/** Frame shared by the composite shader and the browser proof. */

export const LOGO_ASPECT = 1024 / 1536;

/** UV origin is the bottom-left of the viewport. The bottom lane is reserved for type. */
export const FRAME_ORIGIN = { x: 0, y: 0.125 };
export const FRAME_SPAN = { x: 1, y: 0.855 };

export interface ContentRect {
  x: number;
  yFromBottom: number;
  w: number;
  h: number;
}

export function logoContentRect(width: number, height: number): ContentRect {
  const frameW = width * FRAME_SPAN.x;
  const frameH = height * FRAME_SPAN.y;
  const frameX = width * FRAME_ORIGIN.x;
  const frameY = height * FRAME_ORIGIN.y;
  const frameAspect = frameW / Math.max(frameH, 1);
  const dw = frameAspect > LOGO_ASPECT ? frameH * LOGO_ASPECT : frameW;
  const dh = frameAspect > LOGO_ASPECT ? frameH : frameW / LOGO_ASPECT;
  return {
    x: frameX + (frameW - dw) / 2,
    yFromBottom: frameY + (frameH - dh) / 2,
    w: dw,
    h: dh,
  };
}
