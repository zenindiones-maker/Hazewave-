package com.hazewave.fyahremote

import android.annotation.SuppressLint
import android.content.Context
import android.net.Uri
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

/** Settings live only in app-private SharedPreferences on the phone; nothing is hardcoded. */
internal class RemoteSettings(ctx: Context) {
    private val p = ctx.getSharedPreferences("fyahreaper_remote", Context.MODE_PRIVATE)
    var vncUrl: String get() = p.getString("vnc_url", "http://100.113.8.91:6090")!!.trim(); set(v) = p.edit().putString("vnc_url", v.trim()).apply()
    var vncPassword: String get() = p.getString("vnc_password", "")!!.trim(); set(v) = p.edit().putString("vnc_password", v.trim()).apply()
    var hubUrl: String get() = p.getString("hub_url", "http://100.113.8.91:8787")!!.trim(); set(v) = p.edit().putString("hub_url", v.trim()).apply()
    var hubToken: String get() = p.getString("hub_token", "")!!.trim(); set(v) = p.edit().putString("hub_token", v.trim()).apply()
    val configured get() = vncPassword.isNotBlank()
}

/** noVNC page served by websockify on the workstation (tailnet only). */
internal fun noVncPage(base: String, password: String): String =
    Uri.parse(base.trimEnd('/') + "/vnc.html").buildUpon()
        .appendQueryParameter("autoconnect", "1")
        .appendQueryParameter("resize", "scale")
        .appendQueryParameter("reconnect", "1")
        .appendQueryParameter("reconnect_delay", "1500")
        .appendQueryParameter("show_dot", "1")
        .appendQueryParameter("path", "websockify")
        .appendQueryParameter("password", password)
        .build().toString()

/** noVNC can compute its scale while the WebView is still 0x0 (canvas ends up 0px wide). Re-trigger its
 *  resize handling until the canvas has a real size. */
internal const val FIT_WATCHDOG_JS = "(function(){if(window.__fyahFit)return;window.__fyahFit=1;" +
    // In Android WebView noVNC's #noVNC_container can resolve to 0px height; pin it to the real viewport.
    "function fit(){var k=document.getElementById('noVNC_container');if(k){k.style.position='fixed';k.style.left='0';k.style.top='0';" +
    "k.style.width=window.innerWidth+'px';k.style.height=window.innerHeight+'px';}" +
    "var c=document.querySelector('#noVNC_container canvas');if(c&&(c.clientWidth===0||c.clientHeight===0))window.dispatchEvent(new Event('resize'));}" +
    "window.addEventListener('resize',function(){setTimeout(fit,50)});fit();setInterval(fit,700);})()"

internal const val NOVNC_STATUS_JS = "(function(){var d=document.documentElement.classList;var s=(document.getElementById('noVNC_status')||{}).textContent||'';" +
    "var c=document.querySelector('#noVNC_container canvas');var cred=document.getElementById('noVNC_credentials_dlg');" +
    "var needPw=cred&&cred.classList.contains('noVNC_open');" +
    "return (d.contains('noVNC_connected')?'conectado':(d.contains('noVNC_connecting')?'conectando':'desconectado'))+(needPw?' · PEDE SENHA':'')+' · '+s.trim().slice(0,80)+(c?' · tela '+c.clientWidth+'x'+c.clientHeight:'');})()"

// JS helpers operating on the noVNC page's own controls (ids from noVNC vnc.html).
private fun clickJs(id: String) = "(function(){var b=document.getElementById('$id');if(b){b.click();return 'ok'}return 'missing'})()"
private fun shiftJs(down: Boolean): String {
    val type = if (down) "keydown" else "keyup"
    return "(function(){var c=document.querySelector('#noVNC_container canvas')||document.querySelector('canvas');if(!c)return 'missing';" +
        "c.dispatchEvent(new KeyboardEvent('$type',{key:'Shift',code:'ShiftLeft',keyCode:16,which:16,bubbles:true}));return 'ok'})()"
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
internal fun RealReaperScreen(onOpenNative: () -> Unit) {
    val ctx = LocalContext.current
    val prefs = remember { RemoteSettings(ctx) }
    var showSettings by remember { mutableStateOf(!prefs.configured) }
    var reloadKey by remember { mutableIntStateOf(0) }
    var webView by remember { mutableStateOf<WebView?>(null) }
    var barOpen by remember { mutableStateOf(true) }
    var ctrl by remember { mutableStateOf(false) }
    var alt by remember { mutableStateOf(false) }
    var shift by remember { mutableStateOf(false) }
    var state by remember { mutableStateOf("—") }
    var busy by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val diagLog = remember { mutableStateListOf<String>() }
    fun diag(msg: String) { diagLog.add(0, msg); while (diagLog.size > 40) diagLog.removeAt(diagLog.size - 1) }
    var showDiag by remember { mutableStateOf(false) }
    var vncStatus by remember { mutableStateOf("—") }
    var hubStatus by remember { mutableStateOf("—") }
    var testReport by remember { mutableStateOf("") }

    fun hub(): ReaHub? = runCatching {
        if (prefs.hubToken.isBlank()) null else ReaHub(prefs.hubUrl, prefs.hubToken)
    }.getOrNull()

    fun call(path: String) {
        val h = hub() ?: run { scope.launch { snackbar.showSnackbar("Configure o token do ReaHub") }; return }
        scope.launch {
            busy = true
            try { state = JSONObject(h.request(path, "POST")).optString("state", state) }
            catch (e: Exception) { snackbar.showSnackbar(e.message ?: "Falha de rede") }
            finally { busy = false }
        }
    }
    // Truthful transport state from the real REAPER (no fake data) + self-diagnostics.
    LaunchedEffect(reloadKey, showSettings) {
        while (true) {
            val h = hub()
            if (h == null) hubStatus = "sem token" else try {
                val j = JSONObject(h.request("/health")); state = j.getString("state"); hubStatus = "OK (${j.optString("state")})"
            } catch (e: Exception) { state = "offline"; hubStatus = "ERRO: ${e.message?.take(120)}" }
            webView?.evaluateJavascript(NOVNC_STATUS_JS) { v -> vncStatus = v?.trim('"') ?: "?" }
            delay(1500)
        }
    }
    suspend fun testConnection(): String = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        val http = okhttp3.OkHttpClient.Builder().callTimeout(8, java.util.concurrent.TimeUnit.SECONDS).build()
        fun probe(label: String, url: String, token: String? = null): String = try {
            val b = okhttp3.Request.Builder().url(url); if (token != null) b.header("Authorization", "Bearer $token")
            http.newCall(b.build()).execute().use { r -> "$label: HTTP ${r.code}" + if (r.code == 200) " ✓" else " ✗ ${r.body?.string()?.take(80)}" }
        } catch (e: Exception) { "$label: FALHA ${e.javaClass.simpleName}: ${e.message?.take(100)}" }
        listOf(
            probe("noVNC página", prefs.vncUrl.trimEnd('/') + "/vnc.html"),
            probe("ReaHub sem token (espera 401)", prefs.hubUrl.trimEnd('/') + "/health"),
            probe("ReaHub com token", prefs.hubUrl.trimEnd('/') + "/health", prefs.hubToken),
            "senha VNC: " + (if (prefs.vncPassword.isBlank()) "VAZIA ✗" else "${prefs.vncPassword.length} caracteres"),
            "noVNC estado: $vncStatus",
            "WebView: " + (android.webkit.WebView.getCurrentWebViewPackage()?.let { "${it.packageName} ${it.versionName}" } ?: "?"),
        ).joinToString("\n")
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }, containerColor = Color.Black) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            if (!showSettings) {
                key(reloadKey) {
                    AndroidView(modifier = Modifier.fillMaxSize(), factory = { c ->
                        WebView(c).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.useWideViewPort = true
                            settings.loadWithOverviewMode = true
                            settings.builtInZoomControls = false
                            settings.mediaPlaybackRequiresUserGesture = false
                            webViewClient = object : WebViewClient() {
                                override fun onPageFinished(view: WebView, url: String?) { view.evaluateJavascript(FIT_WATCHDOG_JS, null); diag("page loaded") }
                                override fun onReceivedError(v: WebView, r: android.webkit.WebResourceRequest, e: android.webkit.WebResourceError) {
                                    diag("LOAD ERROR ${e.errorCode} ${e.description} ${r.url.path}")
                                }
                                override fun onReceivedHttpError(v: WebView, r: android.webkit.WebResourceRequest, e: android.webkit.WebResourceResponse) {
                                    if (r.isForMainFrame || e.statusCode >= 500) diag("HTTP ${e.statusCode} ${r.url.path}")
                                }
                            }
                            webChromeClient = object : WebChromeClient() {
                                override fun onConsoleMessage(m: android.webkit.ConsoleMessage): Boolean {
                                    android.util.Log.i("FyahWebView", "${m.messageLevel()} ${m.message()} @${m.sourceId()}:${m.lineNumber()}")
                                    if (m.messageLevel() == android.webkit.ConsoleMessage.MessageLevel.ERROR || m.messageLevel() == android.webkit.ConsoleMessage.MessageLevel.WARNING)
                                        diag("JS ${m.messageLevel()}: ${m.message().take(160)}")
                                    return true
                                }
                            }
                            if ((c.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) WebView.setWebContentsDebuggingEnabled(true)
                            loadUrl(noVncPage(prefs.vncUrl, prefs.vncPassword))
                            webView = this
                        }
                    })
                }
            }
            // Slim collapsible overlay bar
            Column(Modifier.align(Alignment.TopEnd).padding(4.dp), horizontalAlignment = Alignment.End) {
                FilledTonalButton(onClick = { barOpen = !barOpen }, contentPadding = PaddingValues(horizontal = 10.dp)) {
                    Text(if (barOpen) "▸" else "◂ $state", color = Color.White)
                }
                if (barOpen) {
                    // Two columns so every control (>=48dp) fits the A15 landscape height (~432dp); scrolls if smaller.
                    Column(Modifier.background(Color(0xCC1E1E24)).padding(4.dp)
                        .verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        val stateColor = when (state) { "recording" -> Color(0xFFFF4040); "playing" -> Color(0xFF52D16A); "offline" -> Color.Gray; else -> Color(0xFFDDDDDD) }
                        Text(state.uppercase(), color = stateColor, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            BarBtn("PLAY", Color(0xFF2E7D32), !busy) { call("/api/transport/play") }
                            BarBtn("STOP", Color(0xFF455A64), !busy) { call("/api/transport/stop") }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            BarBtn("REC", if (state == "recording") Color(0xFFFF1744) else Color(0xFFB71C1C), !busy) { call("/api/transport/rec") }
                            BarBtn("UNDO", Color(0xFF37474F), !busy) { call("/api/edit/undo") }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Toggle("CTRL", ctrl) { ctrl = !ctrl; webView?.evaluateJavascript(clickJs("noVNC_toggle_ctrl_button"), null) }
                            Toggle("ALT", alt) { alt = !alt; webView?.evaluateJavascript(clickJs("noVNC_toggle_alt_button"), null) }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Toggle("SHIFT", shift) { shift = !shift; webView?.evaluateJavascript(shiftJs(shift), null) }
                            BarBtn("ESC", Color(0xFF37474F), true) { webView?.evaluateJavascript(clickJs("noVNC_send_esc_button"), null) }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            BarBtn("⌨", Color(0xFF37474F), true) { webView?.evaluateJavascript(clickJs("noVNC_keyboard_button"), null) }
                            BarBtn("⚙", Color(0xFF37474F), true) { showSettings = true }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            BarBtn("DIAG", if (vncStatus.startsWith("conectado")) Color(0xFF37474F) else Color(0xFFE65100), true) { showDiag = !showDiag }
                            BarBtn("NATIVO", Color(0xFF37474F), true) { onOpenNative() }
                        }
                    }
                }
            }
            if (showDiag) Surface(Modifier.align(Alignment.TopStart).fillMaxWidth(0.62f).fillMaxHeight().padding(6.dp), color = Color(0xEE111116)) {
                Column(Modifier.padding(10.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Diagnóstico", color = Color.White, fontWeight = FontWeight.Bold)
                    Text("REAPER (noVNC): $vncStatus", color = Color.White, fontSize = 13.sp)
                    Text("ReaHub: $hubStatus", color = Color.White, fontSize = 13.sp)
                    Text("noVNC: ${prefs.vncUrl}   ReaHub: ${prefs.hubUrl}", color = Color.LightGray, fontSize = 11.sp)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Button(onClick = { scope.launch { testReport = "testando…"; testReport = testConnection() } }, modifier = Modifier.heightIn(min = 48.dp)) { Text("TESTAR CONEXÃO") }
                        Button(onClick = { reloadKey++ }, modifier = Modifier.heightIn(min = 48.dp)) { Text("RECARREGAR") }
                        Button(onClick = { showDiag = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("FECHAR") }
                    }
                    if (testReport.isNotBlank()) Text(testReport, color = Color(0xFFB2FF59), fontSize = 12.sp)
                    diagLog.forEach { Text(it, color = Color(0xFFFFCC80), fontSize = 11.sp) }
                }
            }
            if (showSettings) SettingsPanel(prefs) { showSettings = false; reloadKey++ }
        }
    }
}


@Composable private fun BarBtn(label: String, color: Color, enabled: Boolean, onClick: () -> Unit) {
    Button(onClick = onClick, enabled = enabled, modifier = Modifier.width(72.dp).heightIn(min = 48.dp),
        contentPadding = PaddingValues(2.dp),
        colors = ButtonDefaults.buttonColors(containerColor = color, contentColor = Color.White)) {
        Text(label, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Color.White)
    }
}

@Composable private fun Toggle(label: String, on: Boolean, onClick: () -> Unit) =
    BarBtn(label, if (on) Color(0xFFFF8F00) else Color(0xFF37474F), true, onClick)

@Composable private fun SettingsPanel(s: RemoteSettings, onDone: () -> Unit) {
    var vnc by remember { mutableStateOf(s.vncUrl) }
    var pw by remember { mutableStateOf(s.vncPassword) }
    var hub by remember { mutableStateOf(s.hubUrl) }
    var tok by remember { mutableStateOf(s.hubToken) }
    Surface(Modifier.fillMaxSize(), color = Color(0xFF15151B)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            val ctx = LocalContext.current
            val ver = remember { runCatching { val i = ctx.packageManager.getPackageInfo(ctx.packageName, 0)
                "${i.versionName} (${if (android.os.Build.VERSION.SDK_INT >= 28) i.longVersionCode else @Suppress("DEPRECATION") i.versionCode.toLong()})" }.getOrDefault("?") }
            Text("FyahReaper Remote · conexão · v$ver", color = Color.White, fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(vnc, { vnc = it }, label = { Text("REAPER (noVNC)") }, singleLine = true, modifier = Modifier.weight(1f))
                OutlinedTextField(pw, { pw = it }, label = { Text("Senha VNC") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.weight(1f))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(hub, { hub = it }, label = { Text("ReaHub") }, singleLine = true, modifier = Modifier.weight(1f))
                OutlinedTextField(tok, { tok = it }, label = { Text("Token ReaHub") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.weight(1f))
            }
            Button(onClick = { s.vncUrl = vnc.trim(); s.vncPassword = pw.trim(); s.hubUrl = hub.trim(); s.hubToken = tok.trim(); onDone() },
                enabled = vnc.trim().startsWith("http") && pw.isNotBlank(), modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("ABRIR REAPER") }
        }
    }
}
