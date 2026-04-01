import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "react-refresh/only-export-components": "off",
      "react-hooks/exhaustive-deps": "off",
      "no-console": ["warn", { "allow": ["error", "warn"] }],
      "no-restricted-properties": ["error", {
        "object": "Math",
        "property": "random",
        "message": "Use crypto.getRandomValues() or crypto.randomUUID() instead of Math.random().",
      }],
      "no-restricted-syntax": ["error",
        {
          "selector": "AssignmentExpression[left.property.name='innerHTML']",
          "message": "Do not assign to innerHTML — use React state-driven rendering to prevent XSS (CASA-41).",
        },
        {
          "selector": "AssignmentExpression[left.computed=true][left.property.value='innerHTML']",
          "message": "Do not assign to innerHTML — use React state-driven rendering to prevent XSS (CASA-41).",
        },
        {
          "selector": "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          "message": "Do not use dangerouslySetInnerHTML — use React state-driven rendering to prevent XSS (CASA-41).",
        },
      ],
    },
  }
);
