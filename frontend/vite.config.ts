// Vite configuration — React dev server, test runner, and build pipeline
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      exclude: ["src/main.tsx", "vite.config.ts"],
      thresholds: {
        lines: 80,
      },
    },
  },
});
