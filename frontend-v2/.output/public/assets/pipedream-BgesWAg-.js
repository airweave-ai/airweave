import{j as e}from"./main-BEToz-TC.js";import{u as h}from"./use-docs-content-ogu5VP42.js";function l(i){const n={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...h(),...i.components},{Accordion:s,AccordionGroup:a,Callout:o,CodeBlocks:c,Step:r,Steps:d}=n;return s||t("Accordion"),a||t("AccordionGroup"),o||t("Callout"),c||t("CodeBlocks"),r||t("Step"),d||t("Steps"),e.jsxs(e.Fragment,{children:[e.jsx("div",{style:{textAlign:"center",margin:"2rem 0"},children:e.jsx("img",{src:"/docs/assets/images/auth-providers/pipedream.jpeg",alt:"Pipedream Integration",style:{maxWidth:"300px",borderRadius:"8px"}})}),`
`,e.jsx(n.h2,{children:"Overview"}),`
`,e.jsx(n.p,{children:"Pipedream enables workflow automation with 2,000+ integrated apps. Airweave can leverage your existing Pipedream connections to sync data without requiring users to authenticate again."}),`
`,e.jsx(n.p,{children:"This integration involves two separate OAuth clients:"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Pipedream OAuth client"}),": Allows Airweave to access Pipedream's API"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Source app OAuth clients"}),": Custom OAuth clients you create for each source app (Notion, Google Drive, etc.)"]}),`
`]}),`
`,e.jsx(o,{type:"warning",children:e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Important"}),": Pipedream only exposes credentials for accounts created with your own custom OAuth clients. Default Pipedream OAuth connections use the Proxy API."]})}),`
`,e.jsx(n.h2,{children:"Prerequisites"}),`
`,e.jsx(n.h3,{children:"For Pipedream API access:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"A Pipedream account with API access"}),`
`,e.jsx(n.li,{children:"Pipedream OAuth client credentials (for Airweave to Pipedream authentication)"}),`
`]}),`
`,e.jsx(n.h3,{children:"For source app access:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Custom OAuth clients created in each source app (Notion, Google Drive, etc.)"}),`
`,e.jsx(n.li,{children:"Source app accounts connected to Pipedream using your custom OAuth clients"}),`
`,e.jsx(n.li,{children:"Not accounts connected using Pipedream's default OAuth implementations"}),`
`]}),`
`,e.jsx(n.h2,{children:"Setup Guide"}),`
`,e.jsxs(d,{children:[e.jsxs(r,{title:"Set up Pipedream OAuth client",toc:!0,children:[e.jsx(n.p,{children:"First, configure the OAuth client that allows Airweave to access Pipedream's API:"}),e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:["Log in to ",e.jsx(n.a,{href:"https://pipedream.com",children:"Pipedream"})]}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsx(n.p,{children:"Navigate to your Project Settings"}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsx(n.p,{children:"Create a new OAuth client for Airweave integration"}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsx(n.p,{children:"Configure redirect URIs if required"}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:["Save your ",e.jsx(n.code,{children:"client_id"})," and ",e.jsx(n.code,{children:"client_secret"})]}),`
`,e.jsx("video",{src:"./create_pipedream_api_key.mp4",controls:!0,loop:!0,autoplay:!0,muted:!0,playsinline:!0,style:{aspectRatio:"16 / 9",width:"100%"},children:e.jsx(n.p,{children:"Your browser does not support the video tag."})}),`
`]}),`
`]}),e.jsx(o,{type:"info",children:e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Purpose"}),": This OAuth client enables Airweave to authenticate with Pipedream's API to retrieve your connected account credentials."]})})]}),e.jsx(r,{title:"Connect Pipedream to Airweave",toc:!0,children:e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:["Go to ",e.jsx(n.a,{href:"https://app.airweave.ai/auth-providers",children:"Airweave Auth Providers"})]}),`
`,e.jsx(n.li,{children:'Click "Connect" next to Pipedream'}),`
`,e.jsxs(n.li,{children:["Enter your Pipedream OAuth client credentials:",`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"client_id"})," (from step 1)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"client_secret"})," (from step 1)"]}),`
`]}),`
`]}),`
`,e.jsx(n.li,{children:"Provide a readable name for this connection"}),`
`,e.jsx(n.li,{children:'Click "Save"'}),`
`]})}),e.jsxs(r,{title:"Create custom OAuth clients for source apps",toc:!0,children:[e.jsx(n.p,{children:"For each source app you want to sync (Notion, Google Drive, etc.), you must create custom OAuth clients:"}),e.jsxs(a,{children:[e.jsx(s,{title:"For Notion",children:e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:["Go to ",e.jsx(n.a,{href:"https://developers.notion.com",children:"Notion Developers"})]}),`
`,e.jsx(n.li,{children:"Create a new integration"}),`
`,e.jsx(n.li,{children:"Configure OAuth settings with your redirect URIs"}),`
`,e.jsxs(n.li,{children:["Save the ",e.jsx(n.code,{children:"client_id"})," and ",e.jsx(n.code,{children:"client_secret"})]}),`
`]})}),e.jsx(s,{title:"For Other Apps:",children:e.jsx(n.p,{children:"Follow similar steps for Google Drive, GitHub, or other source integrations."})})]}),e.jsx(o,{type:"warning",children:e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Important"}),": You must use these custom OAuth clients when connecting accounts in Pipedream. Do not use Pipedream's built-in OAuth options."]})})]}),e.jsx(r,{title:"Connect source apps in Pipedream using custom OAuth",toc:!0,children:e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:"In Pipedream, go to your project's connections"}),`
`,e.jsxs(n.li,{children:["For each source app (Notion, Google Drive, etc.):",`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:'Choose "Custom OAuth" option'}),`
`,e.jsx(n.li,{children:"Enter your custom OAuth client credentials from Step 3"}),`
`,e.jsx(n.li,{children:"Complete the OAuth flow to connect your account"}),`
`]}),`
`]}),`
`,e.jsxs(n.li,{children:["Note the ",e.jsx(n.code,{children:"account_id"})," for each connection (format: ",e.jsx(n.code,{children:"apn_xxxxx"}),")"]}),`
`]})}),e.jsxs(r,{title:"Find your connection details",toc:!0,children:[e.jsx(n.p,{children:"To create source connections, you'll need these identifiers:"}),e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"project_id"}),": Found in the URL when viewing your project (e.g., ",e.jsx(n.code,{children:"proj_JPsD74a"}),")"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"account_id"}),": Retrieved via Pipedream UI or API"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"external_user_id"}),": Retrieved via Pipedream UI or API"]}),`
`]}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X GET "https://api.pipedream.com/v1/connect/{project_id}/accounts?include_credentials=true" \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
`})}),e.jsxs(n.p,{children:["The response will include account IDs like ",e.jsx(n.code,{children:"apn_gyha5Ky"}),"."]})]}),e.jsxs(r,{title:"Create Source Connections",toc:!0,children:[e.jsx(n.p,{children:"Create source connections that automatically retrieve credentials from Pipedream:"}),e.jsxs(c,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

# Create a Notion connection using Pipedream credentials
source_connection = client.source_connections.create(
    name="Company Notion Workspace",
    short_name="notion",
    authentication={
        "provider_readable_id": "my-pipedream-connection-xyz789",  # Your Pipedream connection ID
        "provider_config": {
            "project_id": "proj_JPsD74a",      # From Pipedream
            "account_id": "apn_gyha5Ky",       # From Pipedream API
            "external_user_id": "user123",     # Required: unique user identifier
            "environment": "production",        # Optional, defaults to "production"
        }
    }
)

print(f"Created: {source_connection.name}")
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-typescript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY"
});

// Create a Notion connection using Pipedream credentials
const sourceConnection = await client.sourceConnections.create({
  name: "Company Notion Workspace",
  shortName: "notion",
  authentication: {
    providerReadableId: "my-pipedream-connection-xyz789",  // Your Pipedream connection ID
    providerConfig: {
      project_id: "proj_JPsD74a",      // From Pipedream
      account_id: "apn_gyha5Ky",       // From Pipedream API
      external_user_id: "user123",     // Required: unique user identifier
      environment: "production",      // Optional, defaults to "production"
    }
  }
});

console.log(\`Created: \${sourceConnection.name}\`);
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://app.airweave.ai/source-connections' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "name": "Company Notion Workspace",
  "short_name": "notion",
  "authentication": {
    "provider_readable_id": "my-pipedream-connection-xyz789",
    "provider_config": {
      "project_id": "proj_JPsD74a",
      "account_id": "apn_gyha5Ky",
      "environment": "production",
      "external_user_id": "user123"
    }
  }
}'
`})}),e.jsxs(o,{type:"warning",children:[e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Note"}),": API Validation"]}),e.jsx(n.p,{children:"The API now performs validation on auth provider source connections:"}),e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Provider Existence"}),": 404 error if the specified ",e.jsx(n.code,{children:"provider_readable_id"})," doesn't exist"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Source Compatibility"}),": 400 error if the provider doesn't support the specified source"]}),`
`]}),e.jsx(n.p,{children:e.jsx(n.strong,{children:"Example error response when provider doesn't support a source:"})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-json",children:`{
  "detail": "Source 'github' does not support 'pipedream' as an auth provider. Supported providers: []"
}
`})})]})]})]})]}),`
`,e.jsx(n.h2,{children:"How It Works"}),`
`,e.jsx(n.p,{children:"The integration uses two distinct OAuth flows:"}),`
`,e.jsx(n.h3,{children:"OAuth flow overview"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Airweave to Pipedream"}),": Uses your Pipedream OAuth client for API access"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Pipedream to source apps"}),": Uses your custom OAuth clients for each source app"]}),`
`]}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-mermaid",children:`sequenceDiagram
    participant You
    participant Airweave
    participant Pipedream
    participant Notion

    Note over You,Notion: Setup Phase (Two OAuth clients)
    You->>Notion: Create custom OAuth client
    Note over You,Notion: client_id: "notion_abc123"<br/>client_secret: "notion_secret"
    You->>Pipedream: Connect Notion with your OAuth client
    Note over You,Pipedream: Uses notion_abc123, not Pipedream's default
    Pipedream-->>You: project_id: "proj_JPsD74a"<br/>account_id: "apn_gyha5Ky"

    Note over You,Notion: Configure Airweave
    You->>Airweave: Configure Pipedream auth provider
    Note over You,Airweave: Uses your Pipedream OAuth client
    You->>Airweave: POST /source-connections
    Note over You,Airweave: provider_readable_id: "pipedream-prod-xyz789"<br/>project_id: "proj_JPsD74a"<br/>account_id: "apn_gyha5Ky"

    Note over You,Notion: Sync data (Runtime)
    You->>Airweave: Trigger sync
    Airweave->>Pipedream: POST /oauth/token
    Note over Airweave,Pipedream: Uses your Pipedream OAuth client
    Pipedream-->>Airweave: Access token (1hr expiry)
    Airweave->>Pipedream: GET /connect/proj_JPsD74a/accounts/apn_gyha5Ky
    Note over Airweave,Pipedream: include_credentials=true
    Pipedream-->>Airweave: Notion OAuth credentials
    Note over Pipedream,Airweave: Returns your custom OAuth tokens
    Airweave->>Notion: Sync with credentials
    Notion-->>Airweave: Pages & databases
    Airweave-->>You: ✓ Sync complete
`})}),`
`,e.jsx(n.h2,{children:"Field Mappings"}),`
`,e.jsx(n.p,{children:"Pipedream uses different field names for some credentials:"}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Airweave Field"}),e.jsx(n.th,{children:"Pipedream Field"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"access_token"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"oauth_access_token"})})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"refresh_token"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"oauth_refresh_token"})})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"client_id"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"oauth_client_id"})})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"client_secret"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"oauth_client_secret"})})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"api_key"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"api_key"})})]})]})]}),`
`,e.jsx(n.p,{children:"These mappings are handled automatically."}),`
`,e.jsx(n.h2,{children:"Token Management"}),`
`,e.jsx(n.p,{children:"Pipedream OAuth tokens have specific characteristics:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Expiry"}),": Access tokens expire after 3600 seconds (1 hour)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Auto-refresh"}),": Airweave refreshes tokens 5 minutes before expiry"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Concurrency"}),": Token refresh is thread-safe with async locks"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Grant Type"}),": Uses ",e.jsx(n.code,{children:"client_credentials"})," flow"]}),`
`]}),`
`,e.jsx(n.h2,{children:"Proxy Authentication"}),`
`,e.jsxs(n.p,{children:["When you connect accounts using Pipedream's default OAuth clients, credentials aren't directly exposed for security reasons. Instead, Airweave automatically routes API requests through ",e.jsx(n.a,{href:"https://pipedream.com/docs/connect/api-proxy",children:"Pipedream's proxy endpoint"}),", where the actual credentials are injected server-side. This happens transparently - sources continue using the same HTTP client interface whether they're accessing credentials directly (custom OAuth) or through the proxy (default OAuth). The system automatically detects which mode to use based on the OAuth client type, ensuring your data syncs work seamlessly regardless of how the account was connected in Pipedream."]}),`
`,e.jsx(n.h2,{children:"Troubleshooting"}),`
`,e.jsx(n.h3,{children:e.jsx(n.code,{children:"Credentials not available"})}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`Detail: Credentials not available. Pipedream only exposes credentials for
accounts created with custom OAuth clients, not default Pipedream OAuth.
`})}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Root cause"}),": The account was connected using Pipedream's built-in OAuth client instead of your custom OAuth client."]}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Solution"}),":"]}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:"Disconnect the account in Pipedream"}),`
`,e.jsx(n.li,{children:'Reconnect using "Custom OAuth" option with your own OAuth client credentials'}),`
`,e.jsx(n.li,{children:"Ensure you're using the OAuth client you created in the source app (e.g., Notion Developer Portal)"}),`
`]}),`
`,e.jsx(n.h3,{children:e.jsx(n.code,{children:"Account app mismatch"})}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`Detail: Account apn_xxx is not for app 'notion'
`})}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Solution"}),": Verify the ",e.jsx(n.code,{children:"account_id"})," corresponds to the correct integration type and was created with the right custom OAuth client."]}),`
`,e.jsxs(n.h3,{children:[e.jsx(n.code,{children:"Failed to refresh token"})," (Airweave to Pipedream)"]}),`
`,e.jsx(n.p,{children:"This affects the connection between Airweave and Pipedream's API:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Check if your Pipedream OAuth client credentials are valid"}),`
`,e.jsx(n.li,{children:"Ensure your Pipedream OAuth client is active"}),`
`,e.jsx(n.li,{children:"Verify network connectivity to Pipedream API"}),`
`]}),`
`,e.jsxs(n.h3,{children:[e.jsx(n.code,{children:"Failed to refresh token"})," (Source App Authentication)"]}),`
`,e.jsx(n.p,{children:"This affects the source app tokens retrieved from Pipedream:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Verify your source app OAuth client (e.g., Notion, Google Drive) is still active"}),`
`,e.jsx(n.li,{children:"Check if the source app tokens have been revoked"}),`
`,e.jsx(n.li,{children:"Ensure the source app OAuth client has required permissions"}),`
`]}),`
`,e.jsx(n.h3,{children:e.jsx(n.code,{children:"Missing required auth fields"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"The integration may require fields not provided by your custom OAuth implementation"}),`
`,e.jsx(n.li,{children:"Check the field mappings table above"}),`
`,e.jsx(n.li,{children:"Verify the source app OAuth client has all required scopes"}),`
`,e.jsx(n.li,{children:"Ensure your custom OAuth client configuration matches the source app's requirements"}),`
`]}),`
`,e.jsx(n.h2,{children:"API Reference"}),`
`,e.jsx(n.h3,{children:"Create source connection"}),`
`,e.jsxs(c,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

source_connection = client.source_connections.create(
    name="Team Notion",
    short_name="notion",
    provider_readable_id="pipedream-connection-id",
    provider_config={
        "project_id": "proj_JPsD74a",
        "account_id": "apn_gyha5Ky",
        "external_user_id": "user123",
        "environment": "production"         # Optional, defaults to "production"
    }
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-typescript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY"
});

const sourceConnection = await client.sourceConnections.create({
  name: "Team Notion",
  shortName: "notion",
  providerReadableId: "pipedream-connection-id",
  providerConfig: {
    projectId: "proj_JPsD74a",
    accountId: "apn_gyha5Ky",
    externalUserId: "user123",
    environment: "production"      // Optional, defaults to "production"
  }
});
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://app.airweave.ai/source-connections' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "name": "Team Notion",
  "short_name": "notion",
  "provider_readable_id": "pipedream-connection-id",
  "provider_config": {
    "project_id": "proj_JPsD74a",
    "account_id": "apn_gyha5Ky",
    "external_user_id": "user123",
    "environment": "production"
  }
}'
`})})]}),`
`,e.jsx(n.h2,{children:"Limitations"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Dual OAuth setup required"}),": You need to create and manage two separate OAuth clients:"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"One for Pipedream API access (Airweave to Pipedream)"}),`
`,e.jsx(n.li,{children:"One for each source app (Pipedream to Notion/Asana/etc.)"}),`
`]}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Custom OAuth clients only"}),":"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Source app connections must use your own OAuth clients"}),`
`,e.jsx(n.li,{children:"Pipedream's built-in OAuth implementations are not supported"}),`
`,e.jsx(n.li,{children:"Cannot reuse existing accounts connected via Pipedream's default OAuth"}),`
`]}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Token management complexity"}),":"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Pipedream API tokens expire hourly, requiring automatic refresh"}),`
`,e.jsx(n.li,{children:"Source app tokens managed separately through Pipedream"}),`
`,e.jsx(n.li,{children:"Multiple token refresh flows to maintain"}),`
`]}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"API rate limits"}),": Subject to both Pipedream's API limits and source app limits"]}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Credential access"}),": Only available with ",e.jsx(n.code,{children:"include_credentials=true"})," parameter and proper OAuth client setup"]}),`
`]}),`
`]}),`
`,e.jsx(n.h2,{children:"Next Steps"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"/sources",children:"Browse available sources"})}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"/quickstart",children:"Set up your first sync"})}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"/concepts#workflows",children:"Learn about workflow automation"})}),`
`]})]})}function x(i={}){const{wrapper:n}={...h(),...i.components};return n?e.jsx(n,{...i,children:e.jsx(l,{...i})}):l(i)}function t(i,n){throw new Error("Expected component `"+i+"` to be defined: you likely forgot to import, pass, or provide it.")}export{x as default};
