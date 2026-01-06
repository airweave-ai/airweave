import{j as e}from"./main-BEToz-TC.js";import{u as a}from"./use-docs-content-ogu5VP42.js";function d(n){const o={a:"a",code:"code",h2:"h2",h4:"h4",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...a(),...n.components},{Callout:s,CodeBlocks:c,Step:i,Steps:t}=o;return s||r("Callout"),c||r("CodeBlocks"),i||r("Step"),t||r("Steps"),e.jsxs(e.Fragment,{children:[e.jsx("div",{style:{textAlign:"center",margin:"2rem 0"},children:e.jsxs("picture",{children:[e.jsx("source",{media:"(prefers-color-scheme: dark)",srcSet:"/docs/assets/images/auth-providers/composio-dark.svg"}),e.jsx("source",{media:"(prefers-color-scheme: light)",srcSet:"/docs/assets/images/auth-providers/composio-light.svg"}),e.jsx("img",{src:"/docs/assets/images/auth-providers/composio-light.svg",alt:"Composio Integration",style:{maxWidth:"400px"}})]})}),`
`,e.jsx(o.h2,{children:"Overview"}),`
`,e.jsx(o.p,{children:"Composio enables Airweave to access credentials from integrated applications. When your users connect their accounts through Composio, Airweave can automatically retrieve those credentials for data synchronization."}),`
`,e.jsx(o.h2,{children:"Prerequisites"}),`
`,e.jsxs(o.ul,{children:[`
`,e.jsx(o.li,{children:"A Composio account with API access"}),`
`,e.jsx(o.li,{children:"Your Composio API key"}),`
`,e.jsx(o.li,{children:"Connected user accounts in Composio for the sources you want to sync"}),`
`]}),`
`,e.jsx(o.h2,{children:"Setup Guide"}),`
`,e.jsxs(t,{children:[e.jsxs(i,{title:"Get your Composio API Key",toc:!0,children:[e.jsxs(o.ol,{children:[`
`,e.jsxs(o.li,{children:["Log in to your ",e.jsx(o.a,{href:"https://platform.composio.dev",children:"Composio dashboard"})," and navigate to your Project."]}),`
`,e.jsx(o.li,{children:"Go to your Project settings."}),`
`,e.jsx(o.li,{children:"Copy your API key from the Project API Keys."}),`
`]}),e.jsx("video",{src:"./composio_api_key.mp4",controls:!0,loop:!0,autoplay:!0,muted:!0,playsinline:!0,style:{aspectRatio:"16 / 9",width:"100%"},children:e.jsx(o.p,{children:"Your browser does not support the video tag."})})]}),e.jsx(i,{title:"Connect Composio to Airweave",toc:!0,children:e.jsxs(o.ol,{children:[`
`,e.jsxs(o.li,{children:["Go to ",e.jsx(o.a,{href:"https://app.airweave.ai/auth-providers",children:"Airweave Auth Providers"})]}),`
`,e.jsx(o.li,{children:'Click "Connect" next to Composio'}),`
`,e.jsx(o.li,{children:"Enter your API key"}),`
`,e.jsx(o.li,{children:"Provide a readable name for this connection"}),`
`,e.jsx(o.li,{children:'Click "Save"'}),`
`]})}),e.jsxs(i,{title:"Find your connection details",toc:!0,children:[e.jsx(o.p,{children:"To create source connections, you'll need two identifiers from Composio:"}),e.jsxs(o.ol,{children:[`
`,e.jsxs(o.li,{children:[e.jsx(o.code,{children:"auth_config_id"}),": Navigate to your Auth Configs page"]}),`
`,e.jsxs(o.li,{children:[e.jsx(o.code,{children:"account_id"}),": Click on an auth config to see its connected accounts"]}),`
`]}),e.jsx(s,{type:"info",children:e.jsxs(o.p,{children:[e.jsx(o.strong,{children:"Tip"}),": In Composio, one auth config can have multiple connected accounts, allowing you to manage different user connections under the same integration."]})})]}),e.jsxs(i,{title:"Create Source Connections",toc:!0,children:[e.jsx(o.p,{children:"Now you can create source connections that automatically retrieve credentials from Composio:"}),e.jsxs(c,{children:[e.jsx(o.pre,{children:e.jsx(o.code,{className:"language-python",children:`from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

# Create a Google Drive connection using Composio credentials
source_connection = client.source_connections.create(
    name="Sales Team Google Drive",
    short_name="google_drive",
    authentication={
        "provider_readable_id": "my-composio-connection-abc123",  # Your Composio auth provider id
        "provider_config": {
            "auth_config_id": "config_xyz789",  # From Composio dashboard
            "account_id": "account_abc123"      # From Composio dashboard
        }
    }
)

print(f"Created: {source_connection.name}")
`})}),e.jsx(o.pre,{children:e.jsx(o.code,{className:"language-typescript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY"
});

// Create a Google Drive connection using Composio credentials
const sourceConnection = await client.sourceConnections.create({
  name: "Sales Team Google Drive",
  shortName: "google_drive",
  authentication: {
    providerReadableId: "my-composio-connection-abc123",  // Your Composio connection ID
    providerConfig: {
      authConfigId: "config_xyz789",  // From Composio dashboard
      accountId: "account_abc123"     // From Composio dashboard
    }
  }
});

console.log(\`Created: \${sourceConnection.name}\`);
`})}),e.jsx(o.pre,{children:e.jsx(o.code,{className:"language-bash",children:`curl -X POST 'https://app.airweave.ai/source-connections' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "name": "Sales Team Google Drive",
  "short_name": "google_drive",
  "authentication": {
    "provider_readable_id": "my-composio-connection-abc123",
    "provider_config": {
      "auth_config_id": "config_xyz789",
      "account_id": "account_abc123"
    }
  }
}'
`})}),e.jsxs(s,{type:"warning",children:[e.jsxs(o.p,{children:[e.jsx(o.strong,{children:"Note"}),": API Validation"]}),e.jsx(o.p,{children:"The API now performs validation on auth provider source connections:"}),e.jsxs(o.ol,{children:[`
`,e.jsxs(o.li,{children:[e.jsx(o.strong,{children:"Provider Existence"}),": 404 error if the specified ",e.jsx(o.code,{children:"provider_readable_id"})," doesn't exist"]}),`
`,e.jsxs(o.li,{children:[e.jsx(o.strong,{children:"Source Compatibility"}),": 400 error if the provider doesn't support the specified source"]}),`
`]}),e.jsx(o.p,{children:e.jsx(o.strong,{children:"Example error response when provider doesn't support a source:"})}),e.jsx(o.pre,{children:e.jsx(o.code,{className:"language-json",children:`{
  "detail": "Source 'github' does not support 'composio' as an auth provider. Supported providers: []"
}
`})})]})]})]})]}),`
`,e.jsx(o.h2,{children:"How It Works"}),`
`,e.jsx(o.pre,{children:e.jsx(o.code,{className:"language-mermaid",children:`sequenceDiagram
    participant You
    participant Airweave
    participant Composio
    participant GoogleDrive as Google Drive

    Note over You,GoogleDrive: Setup Phase
    You->>Composio: Connect Google Drive
    Composio-->>You: auth_config_id: "config_xyz789"<br/>account_id: "account_abc123"

    Note over You,GoogleDrive: Create Source Connection
    You->>Airweave: POST /source-connections
    Note over You,Airweave: provider_readable_id: "composio-prod-abc123"<br/>auth_config_id: "config_xyz789"<br/>account_id: "account_abc123"

    Note over You,GoogleDrive: Sync Data
    You->>Airweave: Trigger sync
    Airweave->>Composio: GET /connected_accounts
    Note over Airweave,Composio: Filter by auth_config_id & account_id
    Composio-->>Airweave: OAuth credentials
    Airweave->>GoogleDrive: Sync with credentials
    GoogleDrive-->>Airweave: Documents & files
    Airweave-->>You: ✓ Sync complete
`})}),`
`,e.jsx(o.h2,{children:"Field Mappings"}),`
`,e.jsx(o.p,{children:"Some sources use different field names between Airweave and Composio:"}),`
`,e.jsxs(o.table,{children:[e.jsx(o.thead,{children:e.jsxs(o.tr,{children:[e.jsx(o.th,{children:"Airweave Field"}),e.jsx(o.th,{children:"Composio Field"})]})}),e.jsxs(o.tbody,{children:[e.jsxs(o.tr,{children:[e.jsx(o.td,{children:e.jsx(o.code,{children:"api_key"})}),e.jsx(o.td,{children:e.jsx(o.code,{children:"generic_api_key"})})]}),e.jsxs(o.tr,{children:[e.jsx(o.td,{children:e.jsx(o.code,{children:"google_drive"})}),e.jsx(o.td,{children:e.jsx(o.code,{children:"googledrive"})})]}),e.jsxs(o.tr,{children:[e.jsx(o.td,{children:e.jsx(o.code,{children:"google_calendar"})}),e.jsx(o.td,{children:e.jsx(o.code,{children:"googlecalendar"})})]}),e.jsxs(o.tr,{children:[e.jsx(o.td,{children:e.jsx(o.code,{children:"outlook_mail"})}),e.jsx(o.td,{children:e.jsx(o.code,{children:"outlook"})})]}),e.jsxs(o.tr,{children:[e.jsx(o.td,{children:e.jsx(o.code,{children:"onedrive"})}),e.jsx(o.td,{children:e.jsx(o.code,{children:"one_drive"})})]})]})]}),`
`,e.jsx(o.p,{children:"These mappings are handled automatically by Airweave."}),`
`,e.jsx(o.h2,{children:"Troubleshooting"}),`
`,e.jsx(o.h4,{children:e.jsx(o.code,{children:"No matching connection found"})}),`
`,e.jsxs(o.ul,{children:[`
`,e.jsxs(o.li,{children:["Verify the ",e.jsx(o.code,{children:"auth_config_id"})," and ",e.jsx(o.code,{children:"account_id"})," are correct"]}),`
`,e.jsx(o.li,{children:"Ensure the account is connected in Composio"}),`
`,e.jsxs(o.li,{children:["Check that the integration type matches (e.g., ",e.jsx(o.code,{children:"google_drive"})," vs ",e.jsx(o.code,{children:"googledrive"}),")"]}),`
`]}),`
`,e.jsx(o.h4,{children:e.jsx(o.code,{children:"Missing required auth fields"})}),`
`,e.jsxs(o.ul,{children:[`
`,e.jsx(o.li,{children:"The source may require additional fields not available in Composio"}),`
`,e.jsx(o.li,{children:"Check the field mappings section above"}),`
`,e.jsx(o.li,{children:"Contact support if a mapping is missing"}),`
`]}),`
`,e.jsx(o.h4,{children:e.jsx(o.code,{children:"Authentication failed"})}),`
`,e.jsxs(o.ul,{children:[`
`,e.jsx(o.li,{children:"Verify your Composio API key is valid"}),`
`,e.jsx(o.li,{children:"Check if the user's connection in Composio is still active"}),`
`,e.jsx(o.li,{children:"Ensure the connected account has the necessary permissions"}),`
`]}),`
`,e.jsx(o.h2,{children:"API Reference"}),`
`,e.jsxs(o.p,{children:["For full API details, see the ",e.jsx(o.a,{href:"/api-reference/source-connections/create-source-connections-post",children:"Source Connections API reference"}),"."]})]})}function p(n={}){const{wrapper:o}={...a(),...n.components};return o?e.jsx(o,{...n,children:e.jsx(d,{...n})}):d(n)}function r(n,o){throw new Error("Expected component `"+n+"` to be defined: you likely forgot to import, pass, or provide it.")}export{p as default};
