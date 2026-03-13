import type { PlaygroundConfig } from "../hooks/usePlaygroundState";
import { DEFAULT_DARK, DEFAULT_LIGHT } from "../hooks/usePlaygroundState";

function diffColors(
  current: Record<string, string>,
  defaults: Record<string, string>
): [string, string][] {
  return Object.entries(current).filter(([k, v]) => v !== defaults[k]);
}

function modalStyleBlock(config: PlaygroundConfig): string {
  const m = config.modal;
  const parts: string[] = [];
  if (m.borderRadius !== 16) parts.push(`borderRadius: "${m.borderRadius}px"`);
  if (m.shadow !== "lg") {
    const shadowMap: Record<string, string> = {
      none: "none",
      sm: "0 1px 2px rgba(0,0,0,.05)",
      md: "0 4px 6px rgba(0,0,0,.1)",
      lg: "0 10px 15px rgba(0,0,0,.1)",
      xl: "0 25px 50px rgba(0,0,0,.25)",
    };
    parts.push(`boxShadow: "${shadowMap[m.shadow]}"`);
  }
  return parts.length > 0 ? parts.join(", ") : "";
}

// ---------------------------------------------------------------------------
// Server-side: Python (Flask)
// ---------------------------------------------------------------------------

export function generatePythonServer(config: PlaygroundConfig, isNewCollection = false): string {
  const intFilter = config.allowedIntegrations.length > 0
    ? `\n    "allowed_integrations": ${JSON.stringify(config.allowedIntegrations)},`
    : "";

  const collectionSetup = isNewCollection
    ? `
    # Create a new collection first
    col = requests.post(
        f"{AIRWEAVE_URL}/collections",
        headers={"X-API-Key": AIRWEAVE_API_KEY},
        json={"name": "My Collection"},
    ).json()
    collection_id = col["readable_id"]
`
    : `    collection_id = "my-collection"
`;

  return `from flask import Flask, jsonify
import requests

app = Flask(__name__)

AIRWEAVE_API_KEY = "your_api_key"
AIRWEAVE_URL = "https://api.airweave.ai"

@app.post("/api/connect-session")
def create_session():
${collectionSetup}
    resp = requests.post(
        f"{AIRWEAVE_URL}/connect/sessions",
        headers={"X-API-Key": AIRWEAVE_API_KEY},
        json={
            "readable_collection_id": collection_id,
            "mode": "${config.sessionMode}",${intFilter}
        },
    )
    return jsonify(resp.json())`;
}

// ---------------------------------------------------------------------------
// Server-side: TypeScript (Express)
// ---------------------------------------------------------------------------

export function generateTypeScriptServer(config: PlaygroundConfig, isNewCollection = false): string {
  const intFilter = config.allowedIntegrations.length > 0
    ? `\n      allowed_integrations: ${JSON.stringify(config.allowedIntegrations)},`
    : "";

  const collectionSetup = isNewCollection
    ? `
  // Create a new collection first
  const col = await fetch(\`\${AIRWEAVE_URL}/collections\`, {
    method: "POST",
    headers: {
      "X-API-Key": AIRWEAVE_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name: "My Collection" }),
  }).then((r) => r.json());
  const collectionId = col.readable_id;
`
    : `  const collectionId = "my-collection";
`;

  return `import express from "express";

const app = express();
const AIRWEAVE_API_KEY = "your_api_key";
const AIRWEAVE_URL = "https://api.airweave.ai";

app.post("/api/connect-session", async (req, res) => {
${collectionSetup}
  const resp = await fetch(\`\${AIRWEAVE_URL}/connect/sessions\`, {
    method: "POST",
    headers: {
      "X-API-Key": AIRWEAVE_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      readable_collection_id: collectionId,
      mode: "${config.sessionMode}",${intFilter}
    }),
  });
  res.json(await resp.json());
});`;
}

// ---------------------------------------------------------------------------
// Client-side: React SDK
// ---------------------------------------------------------------------------

export function generateReactClient(config: PlaygroundConfig): string {
  const themeLines: string[] = [];

  if (config.themeMode !== "dark") {
    themeLines.push(`      mode: "${config.themeMode}",`);
  }

  const darkDiff = diffColors(config.darkColors, DEFAULT_DARK);
  const lightDiff = diffColors(config.lightColors, DEFAULT_LIGHT);

  if (darkDiff.length > 0 || lightDiff.length > 0) {
    themeLines.push(`      colors: {`);
    if (darkDiff.length > 0) {
      themeLines.push(`        dark: { ${darkDiff.map(([k, v]) => `${k}: "${v}"`).join(", ")} },`);
    }
    if (lightDiff.length > 0) {
      themeLines.push(`        light: { ${lightDiff.map(([k, v]) => `${k}: "${v}"`).join(", ")} },`);
    }
    themeLines.push(`      },`);
  }

  if (config.logoUrl) {
    themeLines.push(`      options: { logoUrl: "${config.logoUrl}" },`);
  }

  const themeBlock = themeLines.length > 0
    ? `    theme: {\n${themeLines.join("\n")}\n    },\n`
    : "";

  const msBlock = modalStyleBlock(config);
  const modalBlock = msBlock
    ? `    modalStyle: { ${msBlock} },\n`
    : "";

  return `import { useAirweaveConnect } from "@airweave/connect-react";

function App() {
  const { open } = useAirweaveConnect({
    getSessionToken: async () => {
      const res = await fetch("/api/connect-session", {
        method: "POST",
      });
      const { session_token } = await res.json();
      return session_token;
    },
${themeBlock}${modalBlock}    onSuccess: (id) => console.log("Connected:", id),
  });

  return (
    <button onClick={open}>
      Connect your apps
    </button>
  );
}`;
}

// ---------------------------------------------------------------------------
// Client-side: Vanilla JS
// ---------------------------------------------------------------------------

export function generateVanillaClient(config: PlaygroundConfig): string {
  const themeObj: Record<string, unknown> = {};
  if (config.themeMode !== "dark") themeObj.mode = config.themeMode;

  const darkDiff = diffColors(config.darkColors, DEFAULT_DARK);
  const lightDiff = diffColors(config.lightColors, DEFAULT_LIGHT);
  if (darkDiff.length > 0 || lightDiff.length > 0) {
    const colors: Record<string, Record<string, string>> = {};
    if (darkDiff.length > 0) colors.dark = Object.fromEntries(darkDiff);
    if (lightDiff.length > 0) colors.light = Object.fromEntries(lightDiff);
    themeObj.colors = colors;
  }
  if (config.logoUrl) themeObj.options = { logoUrl: config.logoUrl };

  const themeArg = Object.keys(themeObj).length > 0
    ? `\n  theme: ${JSON.stringify(themeObj, null, 4).replace(/\n/g, "\n  ")},`
    : "";

  const msBlock = modalStyleBlock(config);
  const modalArg = msBlock ? `\n  modalStyle: { ${msBlock} },` : "";

  return `import { AirweaveConnect } from "@airweave/connect-js";

const connect = new AirweaveConnect({
  getSessionToken: async () => {
    const res = await fetch("/api/connect-session", {
      method: "POST",
    });
    const { session_token } = await res.json();
    return session_token;
  },${themeArg}${modalArg}
  onSuccess: (id) => console.log("Connected:", id),
});

document.querySelector("#connect-btn")
  .addEventListener("click", () => connect.open());`;
}
