import { defineConfig } from "vite";
import dts from "vite-plugin-dts";
import { resolve } from "path";

export default defineConfig({
  plugins: [
    dts({
      include: ["src"],
      rollupTypes: true,
    }),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      name: "AirweaveConnect",
      formats: ["es", "cjs", "umd", "iife"],
      fileName: (format) => {
        switch (format) {
          case "es":
            return "index.js";
          case "cjs":
            return "index.cjs";
          case "umd":
            return "index.umd.js";
          case "iife":
            return "index.iife.js";
          default:
            return `index.${format}.js`;
        }
      },
    },
    rollupOptions: {
      external: () => false,
    },
    sourcemap: true,
    minify: "esbuild",
  },
});
