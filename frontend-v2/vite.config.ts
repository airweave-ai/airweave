import mdx from "@mdx-js/rollup";
import tailwindcss from "@tailwindcss/vite";
import { devtools } from "@tanstack/devtools-vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";
import path from "path";
import remarkFrontmatter from "remark-frontmatter";
import remarkGfm from "remark-gfm";
import { defineConfig } from "vite";
import viteTsConfigPaths from "vite-tsconfig-paths";
import { componentsGen } from "./src/plugins/vite-plugin-components-gen";

const config = defineConfig({
  plugins: [
    componentsGen(),
    devtools(),
    nitro(),
    viteTsConfigPaths({ projects: ["./tsconfig.json"] }),
    tailwindcss(),
    tanstackStart(),
    // MDX plugin must be placed before viteReact and configured with enforce: 'pre'
    {
      ...mdx({
        remarkPlugins: [remarkGfm, remarkFrontmatter],
        providerImportSource: "@mdx-js/react",
      }),
      enforce: "pre",
    },
    viteReact({
      include: /\.(js|jsx|ts|tsx)$/,
      exclude: /\.mdx$/,
    }),
  ],
  resolve: {
    alias: {
      // Ensure MDX files from fern folder can resolve dependencies
      "@mdx-js/react": path.resolve(__dirname, "node_modules/@mdx-js/react"),
    },
  },
});

export default config;
