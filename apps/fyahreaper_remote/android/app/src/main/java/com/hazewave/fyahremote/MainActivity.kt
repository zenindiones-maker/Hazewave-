package com.hazewave.fyahremote

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import androidx.compose.ui.text.input.PasswordVisualTransformation
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

internal data class Track(val id:String, val name:String, val volume:Float,
                         val mute:Boolean, val solo:Boolean, val armed:Boolean)
internal data class PaintedNote(val pitch:Int, val start:Double, val duration:Double=0.20)

internal class ReaHub(rawUrl:String, rawToken:String) {
    // Pasted values often carry newlines/spaces ("Unexpected char 0x0a in Authorization").
    private val url = rawUrl.trim()
    private val token = rawToken.trim()
    private val http = OkHttpClient()
    init { require(url.startsWith("http://") || url.startsWith("https://")) }
    private fun route(path:String) = url.trimEnd('/') + path
    suspend fun request(path:String, method:String="GET", body:JSONObject?=null):String = withContext(Dispatchers.IO) {
        val requestBody = body?.toString()?.toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url(route(path)).header("Authorization", "Bearer $token")
            .method(method, if (method=="POST" || method=="PATCH")
                (requestBody ?: "{}".toRequestBody("application/json".toMediaType())) else null)
            .build()
        http.newCall(req).execute().use { response ->
            val text = response.body?.string() ?: ""
            if (!response.isSuccessful) throw IOException("HTTP ${response.code}: " + (runCatching { JSONObject(text).optString("detail", text) }.getOrDefault(text)))
            text
        }
    }
    suspend fun tracks():List<Track> {
        val a = JSONArray(request("/api/tracks"))
        return (0 until a.length()).map { i ->
            val t=a.getJSONObject(i)
            Track(t.getString("id"),t.getString("name"),t.getDouble("volume").toFloat(),
                t.getBoolean("mute"),t.getBoolean("solo"),t.getBoolean("armed"))
        }
    }
    suspend fun update(t:Track, key:String, value:Any) {
        request("/api/tracks/${java.net.URLEncoder.encode(t.id, "UTF-8")}","PATCH",JSONObject().put(key,value))
    }
    suspend fun midi(notes:List<PaintedNote>) {
        val array=JSONArray()
        notes.forEach { n -> array.put(JSONObject().put("pitch",n.pitch).put("start",n.start)
            .put("duration",n.duration).put("velocity",100)) }
        request("/api/project/create_midi", "POST",JSONObject().put("notes",array))
    }
    fun ws(onState:(String)->Unit, onError:(String)->Unit):WebSocket {
        val address = route("/ws").replaceFirst("https://","wss://").replaceFirst("http://","ws://")
        val req=Request.Builder().url(address).header("Authorization","Bearer $token").build()
        return http.newWebSocket(req,object:WebSocketListener() {
            override fun onMessage(webSocket:WebSocket, text:String) {
                val json=JSONObject(text)
                if (json.optString("type")=="error") onError("HTTP ${json.optInt("status")}: ${json.optString("detail")}")
                else onState(json.optString("state","unknown"))
            }
            override fun onFailure(webSocket:WebSocket, t:Throwable, response:Response?) { onError(t.message ?: "WebSocket disconnected") }
        })
    }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        // Optional provisioning via launch extras (adb / CI); values are stored only in private prefs.
        intent?.extras?.let { e ->
            val st = RemoteSettings(this)
            e.getString("vnc_url")?.let { st.vncUrl = it.trim() }
            e.getString("vnc_password")?.let { st.vncPassword = it }
            e.getString("hub_url")?.let { st.hubUrl = it }
            e.getString("hub_token")?.let { st.hubToken = it }
        }
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false)
        androidx.core.view.WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(androidx.core.view.WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
        setContent { MaterialTheme(colorScheme=darkColorScheme()) {
            var native by remember { mutableStateOf(false) }
            if (native) Box(Modifier.fillMaxSize()) {
                NativeScreen()
                TextButton(onClick={native=false}, modifier=Modifier.align(androidx.compose.ui.Alignment.TopEnd)) { Text("REAPER ▸", color=Color.White) }
            } else RealReaperScreen(onOpenNative={ native=true })
        } }
    }
}

@Composable internal fun NativeScreen() {
    var host by remember { mutableStateOf("http://100.113.8.91:8787") }
    var token by remember { mutableStateOf("") }
    var hub by remember { mutableStateOf<ReaHub?>(null) }
    var currentState by remember { mutableStateOf("desconectado") }
    var error by remember { mutableStateOf("") }
    var tab by remember { mutableStateOf("Mixer") }
    var tracks by remember { mutableStateOf<List<Track>>(emptyList()) }
    val notes= remember { mutableStateListOf<PaintedNote>() }
    val scope= rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var busy by remember { mutableStateOf(false) }
    fun perform(job:suspend (ReaHub)->Unit) {
        val client=hub ?: return
        scope.launch {
            busy=true
            try { job(client); error="" } catch(e:Exception) {
                error=e.message ?: "Falha de rede"
                snackbar.showSnackbar(error)
            } finally { busy=false }
        }
    }
    // Fallback polling: transport state stays truthful even if the WebSocket is down.
    LaunchedEffect(hub) {
        val client=hub ?: return@LaunchedEffect
        while (true) {
            kotlinx.coroutines.delay(1000)
            try { currentState=JSONObject(client.request("/health")).getString("state") } catch(_:Exception) {}
        }
    }
    DisposableEffect(hub) {
        val socket=hub?.ws(
            onState={ scope.launch(Dispatchers.Main) { currentState=it } },
            onError={ scope.launch(Dispatchers.Main) { error=it } })
        onDispose { socket?.close(1000,"Screen closed") }
    }
    Scaffold(snackbarHost={ SnackbarHost(snackbar) }, containerColor=Color(0xFF101017)) { pad ->
    Column(Modifier.fillMaxSize().padding(pad).padding(16.dp)) {
        Text("HAZEWAVE",fontSize=36.sp,fontWeight=FontWeight.Black,color=Color(0xFFFF6D35))
        Text("FYAHREAPER REMOTE · WORKSTATION",fontSize=12.sp,color=Color.LightGray)
        if (hub==null) {
            Spacer(Modifier.height(28.dp))
            OutlinedTextField(value=host,onValueChange={host=it},label={Text("Endereço da workstation")}, modifier=Modifier.fillMaxWidth())
            OutlinedTextField(value=token,onValueChange={token=it},label={Text("Token de acesso")},visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth())
            Spacer(Modifier.height(12.dp))
            Button(onClick={
                scope.launch {
                    try {
                        val c=ReaHub(host,token)
                        currentState=JSONObject(c.request("/health")).getString("state")
                        tracks=c.tracks()
                        hub=c
                        error=""
                    } catch(e:Exception) { error=e.message ?: "Não foi possível conectar" }
                }
            }, modifier=Modifier.fillMaxWidth().height(64.dp)) { Text("CONECTAR") }
        } else {
            Text("REAPER: $currentState",fontSize=20.sp,fontWeight=FontWeight.Bold,
                color=when(currentState){ "recording"->Color(0xFFFF5A5A); "playing"->Color(0xFF7CE38B); else->Color(0xFFDDDDDD) })
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp),modifier=Modifier.fillMaxWidth()) {
                listOf("play" to "PLAY","stop" to "STOP","rec" to "REC").forEach { (action,label) ->
                    Button(enabled=!busy, onClick={ perform { c ->
                        currentState=JSONObject(c.request("/api/transport/$action","POST")).optString("state",currentState)
                        tracks=c.tracks() } },
                        modifier=Modifier.weight(1f).height(120.dp),
                        colors=ButtonDefaults.buttonColors(containerColor=if(action=="rec") Color(0xFFBB3341) else Color(0xFF3A3A46), contentColor=Color.White)) {
                        Text(label,fontWeight=FontWeight.Bold,fontSize=20.sp,color=Color.White)
                    }
                }
            }
            Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                TextButton(onClick={tab="Mixer"}) { Text("MIXER") }
                TextButton(onClick={tab="Piano"}) { Text("FYAHGRABBER") }
                TextButton(onClick={perform { c->tracks=c.tracks() }}) { Text("ATUALIZAR") }
                TextButton(onClick={hub=null;tracks=emptyList();currentState="desconectado"}) { Text("SAIR") }
            }
            if (tab=="Mixer") {
                LazyColumn(verticalArrangement=Arrangement.spacedBy(12.dp)) {
                    items(tracks,key={it.id}) { t ->
                        Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF24242D), contentColor=Color.White)) {
                            Row(Modifier.fillMaxWidth().padding(12.dp),horizontalArrangement=Arrangement.SpaceBetween) {
                                Column(modifier=Modifier.weight(1f)) {
                                    Text(t.name.ifBlank { "(sem nome)" },fontWeight=FontWeight.Bold,fontSize=18.sp,color=Color.White)
                                    Row {
                                        FilterChip(selected=t.armed,onClick={perform { c->c.update(t,"armed",!t.armed);tracks=c.tracks() }},label={Text("ARM")})
                                        Spacer(Modifier.width(4.dp))
                                        FilterChip(selected=t.mute,onClick={perform { c->c.update(t,"mute",!t.mute);tracks=c.tracks() }},label={Text("MUTE")})
                                        Spacer(Modifier.width(4.dp))
                                        FilterChip(selected=t.solo,onClick={perform { c->c.update(t,"solo",!t.solo);tracks=c.tracks() }},label={Text("SOLO")})
                                    }
                                    Text("${"%.2f".format(t.volume)} linear",color=Color.LightGray)
                                }
                                VerticalFader(t.volume) { volume ->
                                    perform { c->c.update(t,"volume",volume.toDouble());tracks=c.tracks() }
                                }
                            }
                        }
                    }
                }
            } else {
                Text("Selecione um item de áudio no REAPER antes de enviar o MIDI.",color=Color.LightGray)
                Text("Toque nas teclas para pintar as notas em sequência.")
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                    Text("Notas: ${notes.size}")
                    TextButton(onClick={notes.clear()}) { Text("LIMPAR") }
                    Button(enabled=notes.isNotEmpty(),onClick={perform { c->c.midi(notes.toList());notes.clear() }}) { Text("ENVIAR MIDI") }
                }
                LazyColumn {
                    items((36..60).reversed().toList()) { pitch ->
                        Row(Modifier.fillMaxWidth().height(60.dp).padding(bottom=2.dp)
                            .background(if (pitch%12 in listOf(1,3,6,8,10)) Color(0xFF555563) else Color(0xFFF5F5F5),RoundedCornerShape(5.dp))
                            .clickable { if (notes.size<64) notes.add(PaintedNote(pitch,notes.size*0.25)) }
                            .padding(12.dp),horizontalArrangement=Arrangement.SpaceBetween) {
                            Text("MIDI $pitch",color=Color.Black)
                            Text("+ nota",color=Color(0xFFAD462B))
                        }
                    }
                }
            }
        }
        if (error.isNotBlank()) Text(error,color=Color(0xFFFF8B8B),fontSize=12.sp)
    }
    }
}

@Composable private fun VerticalFader(volume:Float, onCommit:(Float)->Unit) {
    var value by remember(volume) { mutableFloatStateOf(volume.coerceIn(0f,2f)) }
    val ratio=(value/2f).coerceIn(0f,1f)
    Canvas(Modifier.width(84.dp).height(230.dp).pointerInput(Unit) {
        detectDragGestures(
            onDragStart={ start -> value=((1f-start.y/size.height.toFloat())*2f).coerceIn(0f,2f) },
            onDragEnd={ onCommit(value) },
            onDrag={ change, _ -> value=((1f-change.position.y/size.height.toFloat())*2f).coerceIn(0f,2f);change.consume() }
        )
    }) {
        val x=size.width/2f
        drawLine(Color.Gray,Offset(x,0f),Offset(x,size.height),strokeWidth=8f,cap=StrokeCap.Round)
        val y=size.height*(1f-ratio)
        drawLine(Color(0xFFFF6D35),Offset(x,size.height),Offset(x,y),strokeWidth=8f)
        drawLine(Color.White,Offset(x-27f,y),Offset(x+27f,y),strokeWidth=13f,cap=StrokeCap.Round)
    }
}
