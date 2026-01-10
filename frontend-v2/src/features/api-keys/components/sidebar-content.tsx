import { DocsContent } from "@/hooks/use-docs-content";

export function ApiKeysDocs() {
  return <DocsContent docPath="quickstart.mdx" />;
}

export function ApiKeysCode() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Using API Keys</h3>
      <p className="text-muted-foreground text-sm">
        Authenticate your requests with your API key:
      </p>
      <pre className="bg-muted overflow-auto rounded-lg p-3 text-xs">
        <code>{`import { AirweaveSDK } from '@airweave/sdk';

const client = new AirweaveSDK({
  apiKey: 'YOUR_API_KEY',
  baseUrl: 'https://api.airweave.ai'
});

// Or use directly in headers
fetch('https://api.airweave.ai/collections', {
  headers: {
    'x-api-key': 'YOUR_API_KEY'
  }
});`}</code>
      </pre>
    </div>
  );
}

export function ApiKeysHelp() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">API Key Security</h3>
      <p className="text-muted-foreground text-sm">
        Keep your API keys secure and never expose them in client-side code.
      </p>
      <div className="space-y-3">
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-medium">Best Practices</h4>
          <ul className="text-muted-foreground mt-1 space-y-1 text-xs">
            <li>Store keys in environment variables</li>
            <li>Rotate keys periodically</li>
            <li>Use different keys for dev/prod</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
