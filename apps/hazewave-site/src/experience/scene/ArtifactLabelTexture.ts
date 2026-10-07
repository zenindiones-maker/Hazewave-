import * as THREE from "three";
import { getArtist } from "../../data/catalog";
import type { Track } from "../../data/catalog";

export function createArtifactLabelTexture(track: Track, accent: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d")!;
  const artist = getArtist(track.artistId);

  ctx.fillStyle = "#070a09";
  ctx.fillRect(0, 0, 512, 512);

  const glow = ctx.createRadialGradient(320, 160, 12, 280, 220, 330);
  glow.addColorStop(0, accent);
  glow.addColorStop(0.22, accent);
  glow.addColorStop(1, "#050706");
  ctx.globalAlpha = 0.18;
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 512, 512);
  ctx.globalAlpha = 1;

  ctx.strokeStyle = accent;
  ctx.globalAlpha = 0.48;
  ctx.lineWidth = 2;

  if (track.artistId === "aether") {
    for (let r = 42; r <= 158; r += 29) {
      ctx.beginPath();
      ctx.arc(330, 205, r, 0, Math.PI * 2);
      ctx.stroke();
    }
  } else if (track.artistId === "monolith") {
    for (let i = 0; i < 6; i += 1) {
      const inset = 56 + i * 24;
      ctx.strokeRect(inset, 88 + i * 9, 400 - i * 48, 260 - i * 18);
    }
  } else {
    for (let i = 0; i < 13; i += 1) {
      const angle = i * 0.73;
      const x = 300 + Math.cos(angle) * (42 + i * 10);
      const y = 205 + Math.sin(angle) * (32 + i * 8);
      ctx.beginPath();
      ctx.arc(x, y, 9 + (i % 3) * 4, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  ctx.globalAlpha = 1;
  ctx.fillStyle = accent;
  ctx.fillRect(38, 38, 78, 6);

  ctx.font = "700 18px Arial, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,.62)";
  ctx.fillText(artist.name.replace(" / DEMO", ""), 38, 86);

  ctx.font = "700 38px Arial, sans-serif";
  ctx.fillStyle = "#f7f3ea";
  ctx.fillText(track.title.toUpperCase(), 38, 392, 430);

  ctx.font = "600 14px ui-monospace, monospace";
  ctx.fillStyle = "rgba(255,255,255,.48)";
  ctx.fillText("HZV // " + track.visual.bpm + " BPM // " + track.id.toUpperCase(), 38, 430);

  ctx.strokeStyle = "rgba(255,255,255,.16)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 18; i += 1) {
    const x = 38 + i * 23;
    const amp = 8 + ((i * 19) % 32);
    ctx.beginPath();
    ctx.moveTo(x, 466 - amp / 2);
    ctx.lineTo(x, 466 + amp / 2);
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}
