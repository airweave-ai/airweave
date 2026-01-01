import { DocsContent } from "@/hooks/use-docs-content";

export function ApiKeysDocs() {
  return <DocsContent docPath="quickstart.mdx" />;
}

export function ApiKeysCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Using API Keys</h3>
      <p className="text-sm text-muted-foreground">
        Authenticate your requests with your API key:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
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
      <h3 className="font-semibold text-base">API Key Security</h3>
      <p className="text-sm text-muted-foreground">
        Keep your API keys secure and never expose them in client-side code.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Best Practices</h4>
          <ul className="text-xs text-muted-foreground mt-1 space-y-1">
            <li>Store keys in environment variables</li>
            <li>Rotate keys periodically</li>
            <li>Use different keys for dev/prod</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
