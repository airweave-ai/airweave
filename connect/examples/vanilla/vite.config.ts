import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5174,
  },
  resolve: {
    alias: {
      "@airweave/connect-js": path.resolve(
        __dirname,
        "../../packages/js/src/index.ts",
      ),
    },
  },
});
