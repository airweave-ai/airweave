import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const OPENAPI_URL = 'https://api.airweave.ai/openapi.json';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, '..');
const outputDir = path.join(frontendRoot, 'openapi');
const outputPath = path.join(outputDir, 'internal-openapi.json');

async function main() {
  const response = await fetch(OPENAPI_URL, {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to download OpenAPI schema: ${response.status} ${response.statusText}`);
  }

  const schema = await response.json();

  await mkdir(outputDir, { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(schema, null, 2)}\n`, 'utf8');

  console.log(`Saved OpenAPI schema to ${outputPath}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
