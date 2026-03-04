// Configuration constants for the MCP server

import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(__dirname, "..", "..", "package.json"), "utf-8"));

export const VERSION: string = pkg.version;
export const DEFAULT_BASE_URL = "https://api.airweave.ai";

export const ERROR_MESSAGES = {
    MISSING_API_KEY: "Error: AIRWEAVE_API_KEY environment variable is required",
    MISSING_COLLECTION: "Error: AIRWEAVE_COLLECTION environment variable is required",
} as const;
