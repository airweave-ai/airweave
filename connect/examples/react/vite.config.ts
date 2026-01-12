import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      "@airweave/connect-react": path.resolve(
        __dirname,
        "../../packages/react/src/index.ts",
      ),
    },
  },
});
