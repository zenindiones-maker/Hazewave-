#!/usr/bin/env bash
# Runs inside reactivecircus/android-emulator-runner. Emulator reaches the host as 10.0.2.2.
set -u
OUT=$PWD/emu-out; mkdir -p $OUT; R=$OUT/results.txt; : > $R
pass(){ echo "PASS $1" | tee -a $R; }; fail(){ echo "FAIL $1" | tee -a $R; }
W=2340; H=1080; CL=$OUT/clicks.log; : > $CL
APP=com.hazewave.fyahremote
shot(){ adb exec-out screencap -p > $OUT/$1.png; }
dims(){ python3 -c "import struct,sys;d=open(sys.argv[1],'rb').read(24);print(*struct.unpack('>II',d[16:24]))" $1; }
# Host side: Xvfb + test window + x11vnc + noVNC + mock ReaHub
Xvfb :99 -screen 0 ${W}x${H}x24 -nolisten tcp & sleep 2
DISPLAY=:99 python3 apps/fyahreaper_remote/ci/click_logger.py $CL $W $H & sleep 3
x11vnc -storepasswd ciPass12 $OUT/vncpass >/dev/null 2>&1
x11vnc -display :99 -rfbport 5999 -rfbauth $OUT/vncpass -forever -shared -noxdamage -o $OUT/x11vnc.log -bg
websockify --web /usr/share/novnc 0.0.0.0:6090 127.0.0.1:5999 > $OUT/websockify.log 2>&1 &
export MOCK_TOKEN=ci-token-0123456789abcdefghijkl MOCK_LOG=$OUT/reahub-calls.log; : > $MOCK_LOG
(cd apps/fyahreaper_remote/ci && python3 -m uvicorn mock_reahub:app --host 0.0.0.0 --port 8787 > $OUT/reahub.log 2>&1 &)
sleep 4; curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:6090/vnc.html | grep -q 200 && pass host_novnc_up || fail host_novnc_up
# Device: A15 geometry, rotation LOCKED in portrait
adb shell wm size 1080x2340; adb shell wm density 400
adb shell settings put system accelerometer_rotation 0; adb shell settings put system user_rotation 0
adb install -r apps/fyahreaper_remote/android/app/build/outputs/apk/debug/app-debug.apk && pass apk_install || fail apk_install
adb shell am start -W -n $APP/.MainActivity --es vnc_url http://10.0.2.2:6090 --es vnc_password ciPass12 \
   --es hub_url http://10.0.2.2:8787 --es hub_token $MOCK_TOKEN
sleep 25; shot 01-launch
read w h < <(dims $OUT/01-launch.png); echo "screenshot ${w}x${h}"
[ "$w" = 2340 ] && [ "$h" = 1080 ] && pass "landscape_with_rotation_lock_portrait(${w}x${h})" || fail "landscape_with_rotation_lock_portrait(${w}x${h})"
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
adb logcat -d -t 400 > $OUT/logcat.txt 2>&1
grep -q "FATAL EXCEPTION" $OUT/logcat.txt && fail no_crash || pass no_crash
cat $R
! grep -q '^FAIL' $R
