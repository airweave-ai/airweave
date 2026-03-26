import type { Config } from 'prettier';

const config: Config = {
  semi: true,
  tabWidth: 2,
  singleQuote: true,
  trailingComma: 'all',
  plugins: ['prettier-plugin-tailwindcss'],
  tailwindStylesheet: 'src/styles.css',
  tailwindFunctions: ['cn', 'cva'],
};

export default config;
