import { defineConfig } from "@playwright/test";

// Las pruebas e2e levantan la API y Vite si no están corriendo (equivalente a `make dev`).
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
  },
  reporter: "list",
  webServer: [
    {
      command: "cd ../backend && uv run uvicorn sinsim.api.app:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/snapshots",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npx vite --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
