import { defineConfig } from "astro/config";

// PixiJS is used only by the isolated P0 cinematic proof route. Keeping its
// chunks explicit prevents an experimental renderer from silently inflating
// the existing website's CORE JavaScript budget.
export default defineConfig({
  output: "static",
  build: { inlineStylesheets: "auto" },
  vite: {
    build: {
      target: "es2022",
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("/node_modules/pixi.js/") || id.includes("/node_modules/@pixi/")) return "wave-p0-pixi-v8";
            if (id.includes("/node_modules/gsap/")) return "wave-p0-gsap";
          }
        }
      }
    }
  }
});
