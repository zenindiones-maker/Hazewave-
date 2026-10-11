#!/usr/bin/env bash
# Runs inside reactivecircus/android-emulator-runner. Emulator reaches the host as 10.0.2.2.
set -u
cleanup(){ pkill -f click_logger.py; pkill -x x11vnc; pkill -f websockify; pkill -f 'uvicorn mock_reahub'; pkill -f 'Xvfb :99'; true; }
trap cleanup EXIT
OUT=$PWD/emu-out; mkdir -p $OUT; R=$OUT/results.txt; : > $R
pass(){ echo "PASS $1" | tee -a $R; }; fail(){ echo "FAIL $1" | tee -a $R; }
W=2340; H=1080; CL=$OUT/clicks.log; : > $CL
APP=com.hazewave.fyahremote
shot(){ adb exec-out screencap -p > $OUT/$1.png; }
dims(){ python3 -c "import struct,sys;d=open(sys.argv[1],'rb').read(24);print(*struct.unpack('>II',d[16:24]))" $1; }
# Host side: Xvfb + test window + x11vnc + noVNC + mock ReaHub
Xvfb :99 -screen 0 ${W}x${H}x24 -nolisten tcp & sleep 2
DISPLAY=:99 python3 apps/fyahreaper_remote/ci/click_logger.py $CL $W $H > $OUT/click_logger.err 2>&1 & sleep 4
DISPLAY=:99 xwininfo -root -tree > $OUT/x-tree.txt 2>&1
ffmpeg -loglevel error -f x11grab -video_size ${W}x${H} -i :99 -frames:v 1 -y $OUT/00-host-display.png
x11vnc -storepasswd ciPass12 $OUT/vncpass >/dev/null 2>&1
x11vnc -display :99 -rfbport 5999 -rfbauth $OUT/vncpass -forever -shared -noxdamage -o $OUT/x11vnc.log -bg
websockify --web /usr/share/novnc 0.0.0.0:6090 127.0.0.1:5999 > $OUT/websockify.log 2>&1 &
export MOCK_TOKEN=ci-token-0123456789abcdefghijkl MOCK_LOG=$OUT/reahub-calls.log; : > $MOCK_LOG
(cd apps/fyahreaper_remote/ci && python3 -m uvicorn mock_reahub:app --host 0.0.0.0 --port 8787 > $OUT/reahub.log 2>&1 &)
sleep 4; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:6090/vnc.html | grep -q 200 && pass host_novnc_up || fail host_novnc_up
# Device: A15 geometry, rotation LOCKED in portrait
adb shell wm size 1080x2340; adb shell wm density 400; sleep 3; adb shell wm size | tee $OUT/wm-size.txt; adb shell wm density | tee -a $OUT/wm-size.txt
adb shell settings put system accelerometer_rotation 0; adb shell settings put system user_rotation 0
D=apps/fyahreaper_remote/android/app/build/outputs/apk/debug
vc(){ adb shell dumpsys package $APP | grep -m1 -o "versionCode=[0-9]*"; }
# 1) Upgrade path: older build (same stable key, lower versionCode) -> new build in place
adb uninstall $APP >/dev/null 2>&1
adb install $D/app-debug-prev.apk && echo "prev $(vc)" | tee $OUT/upgrade.txt
adb install -r $D/app-debug.apk 2>&1 | tee -a $OUT/upgrade.txt | grep -q Success && pass upgrade_install_in_place || fail upgrade_install_in_place
echo "after $(vc)" | tee -a $OUT/upgrade.txt
[ "$(grep -o 'versionCode=[0-9]*' $OUT/upgrade.txt | sort -u | wc -l)" = 2 ] && pass upgrade_versioncode_increased || fail upgrade_versioncode_increased
# 2) Clean install, first launch without provisioning -> new settings screen (not the old CONECTAR screen), landscape
adb uninstall $APP >/dev/null 2>&1
adb install $D/app-debug.apk && pass apk_install || fail apk_install
adb shell am start -W -n $APP/.MainActivity >/dev/null; sleep 6; shot 00-first-run
adb shell uiautomator dump /sdcard/fr.xml >/dev/null; adb pull /sdcard/fr.xml $OUT/first-run.xml >/dev/null
grep -q 'Senha VNC' $OUT/first-run.xml && ! grep -q 'CONECTAR' $OUT/first-run.xml && pass first_run_opens_new_settings_not_old_ui || fail first_run_opens_new_settings_not_old_ui
grep -o 'v0\.[0-9.]*[^"]*' $OUT/first-run.xml | head -1 > $OUT/version-shown.txt; [ -s $OUT/version-shown.txt ] && pass version_shown_in_settings || fail version_shown_in_settings
read w0 h0 < <(dims $OUT/00-first-run.png); [ "$w0" -gt "$h0" ] && pass first_run_landscape || fail first_run_landscape
adb shell am force-stop $APP
# 3) Pasted values with trailing newlines/spaces must be trimmed
NL=$'\n'
# values deliberately carry trailing newline/spaces (like a paste); app must trim them
adb shell "am start -W -n $APP/.MainActivity --es vnc_url 'http://10.0.2.2:6090 ' --es vnc_password 'ciPass12${NL}' --es hub_url ' http://10.0.2.2:8787' --es hub_token '${MOCK_TOKEN}${NL} '"
sleep 25; shot 01-launch
PID=$(adb shell pidof $APP | tr -d '\r'); adb forward tcp:9222 localabstract:webview_devtools_remote_$PID >/dev/null
python3 apps/fyahreaper_remote/ci/cdp_probe.py > $OUT/webview-probe.json 2>&1; cat $OUT/webview-probe.json
grep -q '"connected": *true\|"connected":true' $OUT/webview-probe.json && pass novnc_ui_connected_state || fail novnc_ui_connected_state
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));c=d['canvases'][0];sys.exit(0 if c['cw']>=0.9*d['w'] or c['ch']>=0.9*d['h'] else 1)" $OUT/webview-probe.json && pass remote_canvas_fills_screen || fail remote_canvas_fills_screen
read w h < <(dims $OUT/01-launch.png); echo "screenshot ${w}x${h}"
[ "$w" -gt "$h" ] && pass "landscape_with_rotation_lock_portrait(${w}x${h})" || fail "landscape_with_rotation_lock_portrait(${w}x${h})"
[ "$w" = 2340 ] && [ "$h" = 1080 ] && pass a15_geometry_2340x1080 || fail "a15_geometry_2340x1080(${w}x${h})"
adb shell dumpsys window | grep -E "mCurrentRotation|mRotation=" | head -2 > $OUT/rotation.txt
adb shell dumpsys window | grep -iE "statusBars|navigationBars" | head -6 > $OUT/insets.txt
grep -q "connections.*RFB\|Got connection\|client.*connected\|Client Protocol Version" $OUT/x11vnc.log && pass novnc_connected_from_app || fail novnc_connected_from_app
# Gestures (tap / long-press). Two-finger scroll can't be driven by adb input.
adb shell input tap 700 540; sleep 2
grep -q '^LEFT' $CL && pass tap_is_left_click || fail tap_is_left_click
adb shell input swipe 900 600 900 600 1800; sleep 2
grep -q '^RIGHT' $CL && pass longpress_is_right_click || fail longpress_is_right_click
shot 02-after-gestures
# Side bar (find buttons by text via uiautomator)
adb shell uiautomator dump /sdcard/ui.xml >/dev/null; adb pull /sdcard/ui.xml $OUT/ui.xml >/dev/null
tapText(){ c=$(python3 - "$OUT/ui.xml" "$1" <<'PY'
import re,sys
x=open(sys.argv[1]).read()
for m in re.finditer(r'<node [^>]*>',x):
    n=m.group(0)
    if f'text="{sys.argv[2]}"' in n:
        a=list(map(int,re.findall(r'\d+',re.search(r'bounds="([^"]+)"',n).group(1))));print((a[0]+a[2])//2,(a[1]+a[3])//2);break
PY
); [ -n "$c" ] && adb shell input tap $c; echo "$c"; }
for b in PLAY REC STOP UNDO; do c=$(tapText $b); sleep 2; [ -n "$c" ] || { fail "sidebar_${b}_found"; continue; }; done
grep -q '"play"' $MOCK_LOG && pass sidebar_PLAY_reaches_reahub || fail sidebar_PLAY_reaches_reahub
grep -q '"rec"' $MOCK_LOG && pass sidebar_REC_reaches_reahub || fail sidebar_REC_reaches_reahub
grep -q '"stop"' $MOCK_LOG && pass sidebar_STOP_reaches_reahub || fail sidebar_STOP_reaches_reahub
grep -q '"undo"' $MOCK_LOG && pass sidebar_UNDO_reaches_reahub || fail sidebar_UNDO_reaches_reahub
c=$(tapText ESC); sleep 2; grep -q 'KEY.*Escape' $CL && pass sidebar_ESC_key || fail sidebar_ESC_key
c=$(tapText SHIFT); sleep 2; grep -q 'KEY.*Shift' $CL && pass sidebar_SHIFT_key || fail sidebar_SHIFT_key
tapText SHIFT >/dev/null; sleep 1
c=$(tapText REC); sleep 3; shot 03-recording-state
adb shell uiautomator dump /sdcard/ui2.xml >/dev/null; adb pull /sdcard/ui2.xml $OUT/ui2.xml >/dev/null
grep -q 'text="RECORDING"' $OUT/ui2.xml && pass state_label_shows_RECORDING || fail state_label_shows_RECORDING
tapText STOP >/dev/null; sleep 1
adb shell uiautomator dump /sdcard/u3.xml >/dev/null; adb pull /sdcard/u3.xml $OUT/ui3.xml >/dev/null
c=$(tapText DIAG); sleep 2; adb shell uiautomator dump /sdcard/u4.xml >/dev/null; adb pull /sdcard/u4.xml $OUT/ui4.xml >/dev/null
OUTX=$OUT/ui4.xml; c=$(python3 - "$OUTX" "TESTAR CONEXÃO" <<'PY'
import re,sys
x=open(sys.argv[1]).read()
for m in re.finditer(r'<node [^>]*>',x):
    n=m.group(0)
    if f'text="{sys.argv[2]}"' in n:
        a=list(map(int,re.findall(r'\d+',re.search(r'bounds="([^"]+)"',n).group(1))));print((a[0]+a[2])//2,(a[1]+a[3])//2);break
PY
); [ -n "$c" ] && adb shell input tap $c; sleep 8; shot 05-diagnostics
adb shell uiautomator dump /sdcard/u5.xml >/dev/null; adb pull /sdcard/u5.xml $OUT/ui5.xml >/dev/null
grep -q 'REAPER (noVNC): conectado' $OUT/ui5.xml && pass diag_shows_novnc_connected || fail diag_shows_novnc_connected
grep -q 'ReaHub com token: HTTP 200' $OUT/ui5.xml && pass diag_test_reahub_token_200 || fail diag_test_reahub_token_200
grep -q 'noVNC página: HTTP 200' $OUT/ui5.xml && pass diag_test_novnc_page_200 || fail diag_test_novnc_page_200
adb logcat -d > $OUT/logcat.txt 2>&1; grep FyahWebView $OUT/logcat.txt > $OUT/webview-console.txt
grep -q "FATAL EXCEPTION" $OUT/logcat.txt && fail no_crash || pass no_crash
ffmpeg -loglevel error -f x11grab -video_size ${W}x${H} -i :99 -frames:v 1 -y $OUT/04-host-display-end.png
cat $R
! grep -q '^FAIL' $R
