package com.hazewave.fyahremote

import android.annotation.SuppressLint
import android.content.Context
import android.os.SystemClock
import android.view.MotionEvent
import android.webkit.WebView
import kotlin.math.abs
import kotlin.math.hypot

/** What a finger gesture asks REAPER to do (sent through ReaHub's allowlisted endpoints). */
internal sealed class Gesture {
    data class Action(val name: String, val repeat: Int = 1) : Gesture()
    data class Move(val remotePx: Float, val commit: Boolean) : Gesture()
}

/**
 * WebView hosting noVNC. Single-finger input still reaches noVNC (tap = click, long-press = right click,
 * drag = left drag), but multi-finger gestures are taken away from noVNC and turned into REAPER actions:
 *  - pinch (spread/close) -> zoom in/out, horizontal or vertical depending on the dominant axis
 *  - two-finger pan -> scroll the arrange view
 *  - double-tap -> zoom to the item under the finger (the 2nd tap is swallowed so REAPER never sees a
 *    double-click, which would open item properties)
 *  - MOVE mode: a tap selects the item under the finger, then dragging moves the selected items.
 */
@SuppressLint("ViewConstructor")
internal class TouchWebView(ctx: Context, private val onGesture: (Gesture) -> Unit) : WebView(ctx) {
    var moveMode = false
    /** remote framebuffer pixels per device pixel; updated from the noVNC canvas. */
    var remotePerDevice = 1f
    private val dp = resources.displayMetrics.density

    private var multi = false
    private var baseSpanX = 0f; private var baseSpanY = 0f; private var baseSpan = 0f
    private var lastCx = 0f; private var lastCy = 0f; private var accX = 0f; private var accY = 0f
    private var lastTapUpAt = 0L; private var lastTapX = 0f; private var lastTapY = 0f
    private var downAt = 0L; private var downX = 0f; private var downY = 0f
    private var swallowing = false
    private var dragging = false; private var dragLastX = 0f; private var dragAcc = 0f; private var dragSentAt = 0L

    private fun span(e: MotionEvent): Triple<Float, Float, Float> {
        val sx = abs(e.getX(0) - e.getX(1)); val sy = abs(e.getY(0) - e.getY(1))
        return Triple(sx, sy, hypot(sx, sy))
    }

    private fun cancelToPage(e: MotionEvent) {
        val c = MotionEvent.obtain(e); c.action = MotionEvent.ACTION_CANCEL; super.dispatchTouchEvent(c); c.recycle()
    }

    private fun clickToPage(e: MotionEvent) {
        val t = SystemClock.uptimeMillis()
        val d = MotionEvent.obtain(t, t, MotionEvent.ACTION_DOWN, e.x, e.y, 0); super.dispatchTouchEvent(d); d.recycle()
        val u = MotionEvent.obtain(t, t + 40, MotionEvent.ACTION_UP, e.x, e.y, 0); super.dispatchTouchEvent(u); u.recycle()
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun dispatchTouchEvent(e: MotionEvent): Boolean {
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                multi = false; swallowing = false; dragging = false
                downAt = e.eventTime; downX = e.x; downY = e.y
                if (!moveMode && e.eventTime - lastTapUpAt < 300 && hypot(e.x - lastTapX, e.y - lastTapY) < 30 * dp) {
                    swallowing = true; return true
                }
                if (moveMode) {
                    clickToPage(e)  // select the item under the finger
                    dragging = true; dragLastX = e.x; dragAcc = 0f; dragSentAt = e.eventTime
                    return true
                }
            }
            MotionEvent.ACTION_POINTER_DOWN -> if (e.pointerCount == 2) {
                if (!multi && !swallowing && !dragging) cancelToPage(e)
                if (dragging) { flushDrag(true); dragging = false }
                multi = true; swallowing = false
                val (sx, sy, s) = span(e); baseSpanX = sx; baseSpanY = sy; baseSpan = s
                lastCx = (e.getX(0) + e.getX(1)) / 2; lastCy = (e.getY(0) + e.getY(1)) / 2; accX = 0f; accY = 0f
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                if (multi) { if (e.pointerCount >= 2) multiMove(e); return true }
                if (swallowing) return true
                if (dragging) {
                    dragAcc += (e.x - dragLastX) * remotePerDevice; dragLastX = e.x
                    if (e.eventTime - dragSentAt > 45 && abs(dragAcc) >= 2f) flushDrag(false)
                    return true
                }
            }
            MotionEvent.ACTION_POINTER_UP -> if (multi) return true
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                if (multi) { multi = false; return true }
                if (swallowing) {
                    swallowing = false; lastTapUpAt = 0L
                    if (e.actionMasked == MotionEvent.ACTION_UP) onGesture(Gesture.Action("zoom_item"))
                    return true
                }
                if (dragging) { dragging = false; flushDrag(true); return true }
                if (e.actionMasked == MotionEvent.ACTION_UP && e.eventTime - downAt < 250 && hypot(e.x - downX, e.y - downY) < 12 * dp) {
                    lastTapUpAt = e.eventTime; lastTapX = e.x; lastTapY = e.y
                } else lastTapUpAt = 0L
            }
        }
        return super.dispatchTouchEvent(e)
    }

    private fun flushDrag(commit: Boolean) {
        if (abs(dragAcc) >= 1f || commit) onGesture(Gesture.Move(dragAcc, commit))
        dragAcc = 0f; dragSentAt = SystemClock.uptimeMillis()
    }

    private fun multiMove(e: MotionEvent) {
        val (sx, sy, s) = span(e)
        val ratio = if (baseSpan > 0) s / baseSpan else 1f
        if (ratio > 1.18f || ratio < 0.85f) {
            val horizontal = abs(sx - baseSpanX) >= abs(sy - baseSpanY)
            val name = (if (ratio > 1f) "zoom_in_" else "zoom_out_") + (if (horizontal) "h" else "v")
            onGesture(Gesture.Action(name))
            baseSpanX = sx; baseSpanY = sy; baseSpan = s; accX = 0f; accY = 0f
            lastCx = (e.getX(0) + e.getX(1)) / 2; lastCy = (e.getY(0) + e.getY(1)) / 2
            return
        }
        val cx = (e.getX(0) + e.getX(1)) / 2; val cy = (e.getY(0) + e.getY(1)) / 2
        accX += cx - lastCx; accY += cy - lastCy; lastCx = cx; lastCy = cy
        val step = 56 * dp
        if (abs(accX) >= step && abs(accX) > abs(accY)) {
            val n = (abs(accX) / step).toInt()
            // content follows the fingers: fingers move right -> view scrolls left
            onGesture(Gesture.Action(if (accX > 0) "scroll_left" else "scroll_right", n)); accX -= n * step * Math.signum(accX); accY = 0f
        } else if (abs(accY) >= step && abs(accY) > abs(accX)) {
            val n = (abs(accY) / step).toInt()
            onGesture(Gesture.Action(if (accY > 0) "scroll_up" else "scroll_down", n)); accY -= n * step * Math.signum(accY); accX = 0f
        }
    }
}
