package com.hazewave.fyahremote

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import kotlin.math.log10
import kotlin.math.pow

/** One REAPER track as the mixer shows it (names, order and colours come from REAPER itself). */
internal data class Strip(val id: String, val number: Int, val name: String, val color: Color?, val volume: Float,
                          val pan: Float, val mute: Boolean, val solo: Boolean, val armed: Boolean, val peakDb: Float)

/** Fader law: position 0..1 -> amplitude 0..4 (+12 dB); 0 dB sits at ~71% like a console fader. */
internal fun faderToVol(p: Float) = (p.coerceIn(0f, 1f).pow(4)) * 4f
internal fun volToFader(v: Float) = (v / 4f).coerceIn(0f, 1f).pow(0.25f)
internal fun dbText(v: Float) = if (v <= 1e-6f) "-inf" else "%+.1f".format(20 * log10(v))

/**
 * Touch mixer (BandLab "Mix view" pattern): one wide strip per REAPER track with a tall fader, a pan bar,
 * and 48 dp mute/solo/arm buttons. Values are optimistic while the finger is down and re-synced from REAPER
 * ~6x/s. Double-tap a fader -> 0 dB, double-tap pan -> centre.
 */
@Composable
internal fun MixerPanel(hub: () -> ReaHub?, onClose: () -> Unit, onError: (String) -> Unit) {
    var strips by remember { mutableStateOf<List<Strip>>(emptyList()) }
    var masterPeak by remember { mutableFloatStateOf(-150f) }
    val editing = remember { mutableStateMapOf<String, Pair<Float, Float>>() } // id -> (vol, pan) held by a finger
    val scope = rememberCoroutineScope()
    val pending = remember { mutableStateMapOf<String, JSONObject>() }

    LaunchedEffect(Unit) {
        while (true) {
            val h = hub()
            if (h != null) try {
                val j = JSONObject(h.request("/api/mixer"))
                val a = j.getJSONArray("tracks")
                strips = (0 until a.length()).map { i ->
                    val t = a.getJSONObject(i); val pk = t.getJSONArray("peak_db")
                    Strip(t.getString("id"), t.getInt("number"), t.getString("name"),
                        t.optString("color", "").takeIf { it.startsWith("#") }?.let { Color(android.graphics.Color.parseColor(it)) },
                        t.getDouble("volume").toFloat(), t.getDouble("pan").toFloat(), t.getBoolean("mute"), t.getBoolean("solo"),
                        t.getBoolean("armed"), maxOf(pk.getDouble(0), pk.getDouble(1)).toFloat())
                }
                val m = j.getJSONObject("master").getJSONArray("peak_db"); masterPeak = maxOf(m.getDouble(0), m.getDouble(1)).toFloat()
            } catch (e: Exception) { onError(e.message ?: "mixer") }
            delay(160)
        }
    }
    // Send the newest value per track (coalesced) so a fast fader drag never queues stale requests.
    LaunchedEffect(Unit) {
        while (true) {
            val h = hub()
            if (h != null && pending.isNotEmpty()) {
                val batch = pending.toMap(); batch.keys.forEach { pending.remove(it) }
                for ((id, body) in batch) try {
                    h.request("/api/tracks/" + android.net.Uri.encode(id), "PATCH", body)
                    android.util.Log.i("FyahMixer", "$id $body")
                } catch (e: Exception) { onError(e.message ?: "mixer") }
            }
            delay(40)
        }
    }
    fun send(id: String, k: String, v: Any) { pending[id] = (pending[id] ?: JSONObject()).put(k, v) }

    Column(Modifier.fillMaxSize().background(Color(0xF2121216)).padding(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("MIXER", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp, modifier = Modifier.weight(1f))
            Box(Modifier.size(width = 96.dp, height = 44.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF424242))
                .pointerInput(Unit) { detectTapGestures { onClose() } }, contentAlignment = Alignment.Center) {
                Text("FECHAR", color = Color.White, fontWeight = FontWeight.Bold)
            }
        }
        Row(Modifier.fillMaxSize().horizontalScroll(rememberScrollState()).padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            strips.forEach { s ->
                val held = editing[s.id]
                StripView(s, held?.first ?: s.volume, held?.second ?: s.pan,
                    onVol = { v, done -> editing[s.id] = v to (held?.second ?: s.pan); send(s.id, "volume", v.toDouble()); if (done) scope.launch { delay(400); editing.remove(s.id) } },
                    onPan = { p, done -> editing[s.id] = (held?.first ?: s.volume) to p; send(s.id, "pan", p.toDouble()); if (done) scope.launch { delay(400); editing.remove(s.id) } },
                    onToggle = { k, v -> send(s.id, k, v) })
            }
            MasterMeter(masterPeak)
        }
    }
}

@Composable private fun StripView(s: Strip, vol: Float, pan: Float, onVol: (Float, Boolean) -> Unit, onPan: (Float, Boolean) -> Unit,
                                  onToggle: (String, Boolean) -> Unit) {
    Column(Modifier.width(150.dp).fillMaxHeight().clip(RoundedCornerShape(10.dp)).background(Color(0xFF1E1E26)).padding(5.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Box(Modifier.fillMaxWidth().height(6.dp).background(s.color ?: Color(0xFF607D8B)))
        Text("${s.number}  ${s.name}", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold, maxLines = 1,
            overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            Btn("M", s.mute, Color(0xFFE53935)) { onToggle("mute", !s.mute) }
            Btn("S", s.solo, Color(0xFFFDD835)) { onToggle("solo", !s.solo) }
            Btn("R", s.armed, Color(0xFFD50000)) { onToggle("armed", !s.armed) }
        }
        PanBar(pan, onPan)
        Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            Fader(vol, onVol, Modifier.weight(1f).fillMaxHeight())
            Meter(s.peakDb, Modifier.width(10.dp).fillMaxHeight())
        }
        Text(dbText(vol) + " dB", color = Color(0xFFB0BEC5), fontSize = 12.sp)
    }
}

@Composable private fun Btn(label: String, on: Boolean, onColor: Color, click: () -> Unit) =
    Box(Modifier.size(44.dp, 48.dp).clip(RoundedCornerShape(6.dp)).background(if (on) onColor else Color(0xFF37474F))
        .pointerInput(on) { detectTapGestures { click() } }.semantics { contentDescription = "btn_$label" }, contentAlignment = Alignment.Center) {
        Text(label, color = if (on && label == "S") Color.Black else Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp)
    }

@Composable private fun PanBar(pan: Float, onPan: (Float, Boolean) -> Unit) {
    var w by remember { mutableFloatStateOf(1f) }
    var cur by remember { mutableFloatStateOf(pan) }
    val panNow by rememberUpdatedState(pan); val cb by rememberUpdatedState(onPan)
    Box(Modifier.fillMaxWidth().height(40.dp).clip(RoundedCornerShape(6.dp)).background(Color(0xFF263238))
        .pointerInput(Unit) { detectTapGestures(onDoubleTap = { cb(0f, true) }) }
        .pointerInput(Unit) {
            w = size.width.toFloat()
            detectDragGestures(onDragStart = { cur = panNow }, onDragEnd = { cb(cur, true) }) { ch, d ->
                ch.consume(); cur = (cur + 2f * d.x / w).coerceIn(-1f, 1f); cb(cur, false)
            }
        }) {
        Canvas(Modifier.matchParentSize()) {
            val cx = size.width / 2; val x = cx + pan * cx
            drawRect(Color(0xFF4FC3F7), topLeft = Offset(minOf(cx, x), size.height * 0.35f), size = Size(kotlin.math.abs(x - cx).coerceAtLeast(2f), size.height * 0.3f))
            drawRect(Color.White, topLeft = Offset(x - 3f, 4f), size = Size(6f, size.height - 8f))
        }
        Text(if (kotlin.math.abs(pan) < 0.01f) "C" else if (pan < 0) "${(-pan * 100).toInt()}L" else "${(pan * 100).toInt()}R",
            color = Color.White, fontSize = 11.sp, modifier = Modifier.align(Alignment.BottomCenter))
    }
}

@Composable private fun Fader(vol: Float, onVol: (Float, Boolean) -> Unit, modifier: Modifier) {
    var h by remember { mutableFloatStateOf(1f) }
    var pos by remember { mutableFloatStateOf(volToFader(vol)) }
    val volNow by rememberUpdatedState(vol); val cb by rememberUpdatedState(onVol)
    Box(modifier.clip(RoundedCornerShape(6.dp)).background(Color(0xFF15151B)).border(1.dp, Color(0xFF37474F), RoundedCornerShape(6.dp))
        .pointerInput(Unit) { detectTapGestures(onDoubleTap = { cb(1f, true) }) }
        .pointerInput(Unit) {
            h = size.height.toFloat()
            // Relative drag (finger can start anywhere on the strip), fine control: full travel = 1.4x strip height.
            detectDragGestures(onDragStart = { pos = volToFader(volNow) }, onDragEnd = { cb(faderToVol(pos), true) }) { ch, d ->
                ch.consume(); pos = (pos - d.y / (h * 1.4f)).coerceIn(0f, 1f); cb(faderToVol(pos), false)
            }
        }) {
        Canvas(Modifier.matchParentSize()) {
            val p = volToFader(vol); val cx = size.width / 2
            drawRect(Color(0xFF455A64), topLeft = Offset(cx - 3f, 10f), size = Size(6f, size.height - 20f))
            val zero = size.height - 10f - volToFader(1f) * (size.height - 20f)
            drawLine(Color(0xFF90A4AE), Offset(cx - 22f, zero), Offset(cx + 22f, zero), 2f)
            val y = size.height - 10f - p * (size.height - 20f)
            drawRoundRect(Color(0xFFECEFF1), topLeft = Offset(cx - size.width * 0.38f, y - 22f), size = Size(size.width * 0.76f, 44f), cornerRadius = CornerRadius(8f))
            drawLine(Color(0xFF263238), Offset(cx - size.width * 0.3f, y), Offset(cx + size.width * 0.3f, y), 4f)
        }
    }
}

@Composable private fun Meter(db: Float, modifier: Modifier) = Canvas(modifier.background(Color(0xFF0D0D10))) {
    val p = ((db + 60f) / 66f).coerceIn(0f, 1f)
    drawRect(if (db > -0.5f) Color(0xFFFF5252) else if (db > -12f) Color(0xFFFFEB3B) else Color(0xFF66BB6A),
        topLeft = Offset(0f, size.height * (1 - p)), size = Size(size.width, size.height * p))
}

@Composable private fun MasterMeter(db: Float) =
    Column(Modifier.width(60.dp).fillMaxHeight().clip(RoundedCornerShape(10.dp)).background(Color(0xFF1E1E26)).padding(6.dp),
        horizontalAlignment = Alignment.CenterHorizontally) {
        Text("MASTER", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        Meter(db, Modifier.width(18.dp).weight(1f).padding(vertical = 6.dp))
        Text(if (db < -100) "-inf" else "%.1f".format(db), color = Color(0xFFB0BEC5), fontSize = 11.sp)
    }
