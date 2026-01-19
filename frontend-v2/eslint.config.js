import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

export default defineConfig([
  { ignores: ["dist", ".output", "node_modules", "*.gen.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // Core React Hooks rules
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // Disable React Compiler rules (not using compiler)
      "react-hooks/purity": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/set-state-in-render": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/incompatible-library": "off",
      "react-hooks/use-memo": "off",
      // React Refresh
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // TypeScript rules
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
      // General rules
      "no-console": ["warn", { allow: ["warn", "error", "debug"] }],
    },
  },
  // Disable react-refresh for MDX components and UI library files
  {
    files: [
      "**/mdx/**/*.{ts,tsx}",
      "**/mdx-*.{ts,tsx}",
      "**/components/ui/**/*.{ts,tsx}",
      "**/lib/**/*.{ts,tsx}",
      "**/hooks/**/*.{ts,tsx}",
      "**/stores/**/*.{ts,tsx}",
    ],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
  // Allow console.log in test files
  {
    files: ["**/__tests__/**/*.{ts,tsx}", "**/*.test.{ts,tsx}"],
    rules: {
      "no-console": "off",
      "no-constant-binary-expression": "off",
    },
  },
]);
