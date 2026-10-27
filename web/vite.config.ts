import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run dev` serves the player with hot reload and hands every station route to the station on :7889
const station = process.env.CREEK_STATION ?? "http://127.0.0.1:7889";
const routes = ["/state", "/events", "/now", "/ctl", "/post", "/queue", "/yt", "/search", "/add", "/news",
                "/stream.mp3"];

export default defineConfig({
  plugins: [react()],
  server: { proxy: Object.fromEntries(routes.map((r) => [r, { target: station, changeOrigin: true }])) },
  build: { outDir: "dist", assetsDir: "assets", sourcemap: true },
});
