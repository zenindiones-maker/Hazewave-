package com.hazewave.fyahremote

import android.annotation.SuppressLint
import android.content.Context
import android.os.SystemClock
import android.view.MotionEvent
import android.webkit.WebView
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max

/** What a finger gesture asks REAPER to do (sent through ReaHub's allowlisted endpoints). */
internal sealed class Gesture {
    data class Action(val name: String, val repeat: Int = 1) : Gesture()
    /** Smooth arrange zoom/pan: factor multiplies the zoom around remote x [anchorX]; panPx scrolls with the fingers. */
    data class View(val factor: Float, val anchorX: Int, val panPx: Float) : Gesture()
    /** Direct manipulation of the item under the finger (remote framebuffer px). */
    data class Drag(val phase: String, val x: Int, val y: Int) : Gesture()
}

/**
 * WebView hosting noVNC. Single-finger input still reaches noVNC (tap = click, long-press = right click,
 * drag = left drag). Multi-finger gestures never reach noVNC; they become REAPER view changes:
 *  - horizontal pinch: smooth zoom anchored at the point between the fingers (+ pan as the fingers travel)
 *  - two-finger horizontal pan: smooth scroll; vertical pinch / pan: track-height zoom / vertical scroll
 *  - double-tap: zoom to the item (2nd tap swallowed so REAPER never sees a double-click)
 *  - MOVE mode: nothing reaches noVNC. Drag an item to move it (also across tracks, snapped to grid),
 *    drag near its left/right edge to trim; a tap just selects it.
 */
@SuppressLint("ViewConstructor")
internal class TouchWebView(ctx: Context, private val onGesture: (Gesture) -> Unit) : WebView(ctx) {
    var moveMode = false
    /** remote framebuffer pixels per device pixel; updated from the noVNC canvas. */
    var remotePerDevice = 1f
    /** where the remote framebuffer starts inside this view, in device px (letterboxing). */
    var offX = 0f; var offY = 0f
    /** finger position for local (optimistic) previews: x, y in view px, or null when lifted. */
    var onFinger: ((Float, Float, Boolean) -> Unit)? = null
    private fun rx(x: Float) = max(0, ((x - offX) * remotePerDevice).toInt())
    private fun ry(y: Float) = max(0, ((y - offY) * remotePerDevice).toInt())
    private val dp = resources.displayMetrics.density

    private var multi = false
    private var mode = 0 // 0 undecided, 1 h-zoom/pan, 2 v-zoom, 3 v-pan
    private var startSx = 0f; private var startSy = 0f; private var startCx = 0f; private var startCy = 0f
    private var lastSx = 0f; private var lastCx = 0f; private var accY = 0f; private var baseSy = 0f
    private var lastTapUpAt = 0L; private var lastTapX = 0f; private var lastTapY = 0f
    private var downAt = 0L; private var downX = 0f; private var downY = 0f
    private var swallowing = false
    private var dragging = false; private var dragStarted = false; private var dragSentAt = 0L

    private fun cancelToPage(e: MotionEvent) {
        val c = MotionEvent.obtain(e); c.action = MotionEvent.ACTION_CANCEL; super.dispatchTouchEvent(c); c.recycle()
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
                if (moveMode) { dragging = true; dragStarted = false; return true }
            }
            MotionEvent.ACTION_POINTER_DOWN -> if (e.pointerCount == 2) {
                if (!multi && !swallowing && !dragging) cancelToPage(e)
                if (dragging) { if (dragStarted) { onGesture(Gesture.Drag("cancel", 0, 0)); onFinger?.invoke(0f, 0f, false) }; dragging = false }
                multi = true; swallowing = false; mode = 0
                startSx = abs(e.getX(0) - e.getX(1)); startSy = abs(e.getY(0) - e.getY(1))
                startCx = (e.getX(0) + e.getX(1)) / 2; startCy = (e.getY(0) + e.getY(1)) / 2
                lastSx = startSx; lastCx = startCx; baseSy = startSy; accY = 0f
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                if (multi) { if (e.pointerCount >= 2) multiMove(e); return true }
                if (swallowing) return true
                if (dragging) {
                    if (!dragStarted) {
                        if (hypot(e.x - downX, e.y - downY) < 10 * dp) return true
                        dragStarted = true
                        onGesture(Gesture.Drag("grab", rx(downX), ry(downY)))
                    }
                    onFinger?.invoke(e.x, e.y, true)
                    if (e.eventTime - dragSentAt > 30) { onGesture(Gesture.Drag("drag", rx(e.x), ry(e.y))); dragSentAt = e.eventTime }
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
                if (dragging) {
                    dragging = false
                    if (dragStarted) {
                        onGesture(Gesture.Drag("drag", rx(e.x), ry(e.y)))
                        onGesture(Gesture.Drag(if (e.actionMasked == MotionEvent.ACTION_UP) "end" else "cancel", 0, 0))
                        onFinger?.invoke(e.x, e.y, false)
                    } else if (e.actionMasked == MotionEvent.ACTION_UP) {
                        onGesture(Gesture.Drag("grab", rx(downX), ry(downY))); onGesture(Gesture.Drag("end", 0, 0))  // tap = select
                    }
                    return true
                }
                if (e.actionMasked == MotionEvent.ACTION_UP && e.eventTime - downAt < 250 && hypot(e.x - downX, e.y - downY) < 12 * dp) {
                    lastTapUpAt = e.eventTime; lastTapX = e.x; lastTapY = e.y
                } else lastTapUpAt = 0L
            }
        }
        return super.dispatchTouchEvent(e)
    }

    private fun multiMove(e: MotionEvent) {
        val sx = abs(e.getX(0) - e.getX(1)); val sy = abs(e.getY(0) - e.getY(1))
        val cx = (e.getX(0) + e.getX(1)) / 2; val cy = (e.getY(0) + e.getY(1)) / 2
        if (mode == 0) {
            val dsx = abs(sx - startSx); val dsy = abs(sy - startSy); val dcx = abs(cx - startCx); val dcy = abs(cy - startCy)
            val m = maxOf(dsx, dsy, dcx, dcy)
            if (m < 12 * dp) return
            mode = when (m) { dsx, dcx -> 1; dsy -> 2; else -> 3 }
            lastSx = sx; lastCx = cx; baseSy = sy; accY = 0f
        }
        when (mode) {
            1 -> {
                val f = if (lastSx > 24 * dp && sx > 24 * dp) sx / lastSx else 1f
                val pan = (cx - lastCx) * remotePerDevice
                if (abs(f - 1f) > 0.005f || abs(pan) >= 1f) {
                    onGesture(Gesture.View(f, rx(cx), pan)); lastSx = sx; lastCx = cx
                }
            }
            2 -> {
                val ratio = if (baseSy > 0) sy / baseSy else 1f
                if (ratio > 1.18f || ratio < 0.85f) { onGesture(Gesture.Action(if (ratio > 1f) "zoom_in_v" else "zoom_out_v")); baseSy = sy }
            }
            3 -> {
                accY += cy - startCy; startCy = cy
                val step = 48 * dp
                if (abs(accY) >= step) {
                    val n = (abs(accY) / step).toInt()
                    onGesture(Gesture.Action(if (accY > 0) "scroll_up" else "scroll_down", n)); accY -= n * step * Math.signum(accY)
                }
            }
        }
    }
}
