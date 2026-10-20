/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// El backend sirve la API en 127.0.0.1:8000 (constitución II: solo vía REST).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/lib/test-setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
