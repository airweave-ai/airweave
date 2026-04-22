export type SourceConnectionSdkLanguage = 'node' | 'python';

export interface SourceConnectionSdkSnippet {
  requestCode: string;
  responseCode: string;
}

export const sourceConnectionSdkSnippets = {
  auth: {
    node: {
      requestCode: `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY",
});

const sourceConnection = {
  id: "source-connection-id",
  auth: {
    auth_url: "https://api.airweave.ai/source-connections/authorize/abc123",
    claim_token: "claim-token",
  },
};

window.location.assign(sourceConnection.auth.auth_url);

const verifiedConnection = await client.sourceConnections.verifyOauth(
  sourceConnection.id,
  {
    claim_token: sourceConnection.auth.claim_token,
  },
);`,
      responseCode: `const response = {
  id: "source-connection-id",
  short_name: "your_source_short_name",
  status: "pending_sync",
  auth: {
    authenticated: true,
    authenticated_at: "2026-04-13T10:20:00Z",
    method: "oauth_browser",
  },
  sync: {
    last_job: {
      id: "sync-job-id",
      status: "pending",
    },
    total_runs: 0,
  },
};`,
    },
    python: {
      requestCode: `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
)

source_connection = {
    "id": "source-connection-id",
    "auth": {
        "auth_url": "https://api.airweave.ai/source-connections/authorize/abc123",
        "claim_token": "claim-token",
    },
}

print(source_connection["auth"]["auth_url"])

verified_connection = client.source_connections.verify_oauth(
    source_connection_id=source_connection["id"],
    claim_token=source_connection["auth"]["claim_token"],
)`,
      responseCode: `{
    "id": "source-connection-id",
    "short_name": "your_source_short_name",
    "status": "pending_sync",
    "auth": {
        "authenticated": True,
        "authenticated_at": "2026-04-13T10:20:00Z",
        "method": "oauth_browser",
    },
    "sync": {
        "last_job": {
            "id": "sync-job-id",
            "status": "pending",
        },
        "total_runs": 0,
    },
}`,
    },
  },
  config: {
    node: {
      requestCode: `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY",
});

const sourceConnection = await client.sourceConnections.create({
  name: "Example Connection",
  short_name: "your_source_short_name",
  readable_collection_id: "your-collection-id",
  authentication: {
    redirect_uri: "https://your-app.com/connect-source/auth/callback",
  },
  sync_immediately: false,
});`,
      responseCode: `const response = {
  id: "source-connection-id",
  short_name: "your_source_short_name",
  readable_collection_id: "your-collection-id",
  status: "pending_auth",
  auth: {
    auth_url: "https://api.airweave.ai/source-connections/authorize/abc123",
    claim_token: "claim-token",
    authenticated: false,
    method: "oauth_browser",
  },
};`,
    },
    python: {
      requestCode: `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
)

source_connection = client.source_connections.create(
    name="Example Connection",
    short_name="your_source_short_name",
    readable_collection_id="your-collection-id",
    authentication={
        "redirect_uri": "https://your-app.com/connect-source/auth/callback",
    },
    sync_immediately=False,
)`,
      responseCode: `{
    "id": "source-connection-id",
    "short_name": "your_source_short_name",
    "readable_collection_id": "your-collection-id",
    "status": "pending_auth",
    "auth": {
        "auth_url": "https://api.airweave.ai/source-connections/authorize/abc123",
        "claim_token": "claim-token",
        "authenticated": False,
        "method": "oauth_browser",
    },
}`,
    },
  },
  sync: {
    node: {
      requestCode: `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY",
});

const sourceConnection = await client.sourceConnections.get(
  "source-connection-id",
);

console.log(sourceConnection.sync?.last_job);`,
      responseCode: `const response = {
  id: "source-connection-id",
  status: "syncing",
  sync: {
    last_job: {
      id: "sync-job-id",
      status: "running",
      started_at: "2026-04-13T10:21:00Z",
      entities_inserted: 124,
      entities_updated: 12,
      entities_failed: 0,
    },
    total_runs: 1,
  },
};`,
    },
    python: {
      requestCode: `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
)

source_connection = client.source_connections.get(
    source_connection_id="source-connection-id",
)

print(source_connection.sync["last_job"])`,
      responseCode: `{
    "id": "source-connection-id",
    "status": "syncing",
    "sync": {
        "last_job": {
            "id": "sync-job-id",
            "status": "running",
            "started_at": "2026-04-13T10:21:00Z",
            "entities_inserted": 124,
            "entities_updated": 12,
            "entities_failed": 0,
        },
        "total_runs": 1,
    },
}`,
    },
  },
} satisfies Record<
  'auth' | 'config' | 'sync',
  Record<SourceConnectionSdkLanguage, SourceConnectionSdkSnippet>
>;
