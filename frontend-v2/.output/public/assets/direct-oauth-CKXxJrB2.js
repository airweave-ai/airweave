import{j as e}from"./main-BEToz-TC.js";import{u as s}from"./use-docs-content-ogu5VP42.js";function r(i){const n={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",ul:"ul",...s(),...i.components},{CodeBlocks:t,Note:o}=n;return t||c("CodeBlocks"),o||c("Note"),e.jsxs(e.Fragment,{children:[e.jsx(n.h2,{children:"Overview"}),`
`,e.jsx(n.p,{children:"Direct OAuth allows you to create source connections using the standard OAuth 2.0 browser flow. This method provides a seamless user experience where users authenticate directly through their service provider's consent screen, without needing to manage tokens manually."}),`
`,e.jsx(n.p,{children:"Airweave supports two main approaches for Direct OAuth:"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"URL-based OAuth"}),": Users authenticate through Airweave's hosted OAuth flow"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"BYOC (Bring Your Own Credentials)"}),": Use your own OAuth application credentials"]}),`
`]}),`
`,e.jsx(n.h2,{children:"Supported Connectors"}),`
`,e.jsx(n.p,{children:"Direct OAuth is supported by most Airweave connectors. Some connectors require you to provide your own OAuth application credentials (BYOC), while others can use Airweave's hosted OAuth flow."}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Connectors requiring BYOC:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Dropbox, Gmail, Google Calendar, Google Drive"}),`
`]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Connectors using Direct Authentication only:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Bitbucket, GitHub, PostgreSQL, Stripe, CTTI"}),`
`]}),`
`,e.jsx(o,{children:e.jsx(n.p,{children:"Most connectors also support authentication through external providers like Composio and Pipedream."})}),`
`,e.jsx(n.h2,{children:"URL-based OAuth Flow"}),`
`,e.jsx(n.p,{children:"The URL-based OAuth flow is the simplest way to connect sources. Users are redirected to Airweave's hosted OAuth flow, which handles the entire authentication process."}),`
`,e.jsx("video",{src:"./direct_oauth_notion.mp4",controls:!0,loop:!0,autoplay:!0,muted:!0,playsinline:!0,style:{aspectRatio:"16 / 9",width:"100%"},children:e.jsx(n.p,{children:"Your browser does not support the video tag."})}),`
`,e.jsx(n.h3,{children:"How it works"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Initiate Connection"}),": Create a source connection using the URL-based authentication method"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"User Consent"}),": Users are redirected to the service provider's consent screen"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Token Exchange"}),": Airweave exchanges the authorization code for access and refresh tokens"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Data Sync"}),": The connection is established and data synchronization begins"]}),`
`]}),`
`,e.jsx(n.h3,{children:"Creating a URL-based OAuth connection"}),`
`,e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`from airweave import AirweaveSDK
from airweave.types import OAuthBrowserAuthentication

airweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")

# Create source connection - returns pending connection with auth_url
source_connection = airweave.source_connections.create(
    name="Notion connection",
    short_name="notion",
    readable_collection_id="my-collection-id",
    authentication=OAuthBrowserAuthentication(
        redirect_uri="https://your-app.com/callback"
    ),
    sync_immediately=False  # OAuth browser flows cannot sync immediately
)

# Connection is now in pending state - redirect user to auth_url
print(f"Redirect user to: {source_connection.auth.auth_url}")
print(f"Connection status: {source_connection.status}")  # "pending"
print(f"Authenticated: {source_connection.auth.authenticated}")  # False
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});

// Create source connection - returns pending connection with auth_url
const sourceConnection = await airweave.sourceConnections.create({
    name: "Notion connection",
    shortName: "notion",
    readableCollectionId: "my-collection-id",
    authentication: {
        redirect_uri: "https://your-app.com/callback"
    },
    syncImmediately: false  // OAuth browser flows cannot sync immediately
});

// Connection is now in pending state - redirect user to auth_url
console.log(\`Redirect user to: \${sourceConnection.auth.auth_url}\`);
console.log(\`Connection status: \${sourceConnection.status}\`);  // "pending"
console.log(\`Authenticated: \${sourceConnection.auth.authenticated}\`);  // false
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST https://api.airweave.ai/source-connections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "Notion connection",
  "short_name": "notion",
  "readable_collection_id": "my-collection-id",
  "authentication": {
    "redirect_uri": "https://your-app.com/callback"
  },
  "sync_immediately": false
}'

# Response includes:
# {
#   "id": "connection-id",
#   "status": "pending",
#   "auth": {
#     "authenticated": false,
#     "auth_url": "https://api.airweave.ai/oauth/proxy/...",
#     "auth_url_expires": "2024-01-01T12:00:00Z"
#   }
# }
`})})]}),`
`,e.jsx(n.h3,{children:"Handling the OAuth callback"}),`
`,e.jsx(n.p,{children:"When using URL-based OAuth, you'll receive an authorization URL that you need to redirect users to. After they complete the OAuth flow, they'll be redirected back to your specified callback URL with the necessary parameters."}),`
`,e.jsx(o,{children:e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Important"}),": OAuth browser flows (both standard and BYOC) cannot use ",e.jsx(n.code,{children:"sync_immediately=true"}),". The sync will automatically start after the user completes the OAuth authentication flow. Setting ",e.jsx(n.code,{children:"sync_immediately=true"})," will result in a validation error."]})}),`
`,e.jsx(n.h3,{children:"Redirect URI basics"}),`
`,e.jsxs(n.p,{children:["The ",e.jsx(n.code,{children:"redirect_uri"})," is the URL where the user is sent after granting consent with the provider. It must exactly match an allowed redirect/callback URL configured for the OAuth app. Use it when you want users to return to your application after authentication (typical for hosted OAuth). For BYOC, configure the provider to allow Airweave's callback (",e.jsx(n.code,{children:"https://api.airweave.ai/oauth/callback"}),") and optionally set ",e.jsx(n.code,{children:"redirect_uri"})," so Airweave can forward the user back to your app after the token exchange."]}),`
`,e.jsx(n.h2,{children:"BYOC (Bring Your Own Credentials)"}),`
`,e.jsx(n.p,{children:"BYOC allows you to use your own OAuth application credentials instead of Airweave's hosted OAuth flow. This gives you more control over the authentication process and branding."}),`
`,e.jsx(n.h3,{children:"Benefits of BYOC"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Custom Branding"}),": Use your own OAuth application with your branding"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Enhanced Security"}),": Control your own OAuth application settings"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Compliance"}),": Meet specific compliance requirements for your organization"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Rate Limits"}),": Use your own rate limits instead of shared ones"]}),`
`]}),`
`,e.jsx(n.h3,{children:"Setting up BYOC"}),`
`,e.jsx(n.p,{children:"To use BYOC, you'll need to:"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Create OAuth Application"}),": Set up an OAuth application with the service provider"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Configure Redirect URI"}),": Add Airweave's callback URL to your OAuth application"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Provide Credentials"}),": Use your client ID and client secret in the connection"]}),`
`]}),`
`,e.jsx(n.h3,{children:"How BYOC Detection Works"}),`
`,e.jsxs(n.p,{children:["BYOC (Bring Your Own Credentials) is automatically detected when you provide both ",e.jsx(n.code,{children:"client_id"})," and ",e.jsx(n.code,{children:"client_secret"})," in the ",e.jsx(n.code,{children:"OAuthBrowserAuthentication"})," object. If you provide only one of these fields, the API will return a validation error."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"BYOC Detection Logic:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:["✅ Both ",e.jsx(n.code,{children:"client_id"})," AND ",e.jsx(n.code,{children:"client_secret"})," provided → BYOC mode"]}),`
`,e.jsxs(n.li,{children:["✅ Neither ",e.jsx(n.code,{children:"client_id"})," nor ",e.jsx(n.code,{children:"client_secret"})," provided → Standard OAuth browser flow"]}),`
`,e.jsxs(n.li,{children:["❌ Only ",e.jsx(n.code,{children:"client_id"})," OR only ",e.jsx(n.code,{children:"client_secret"})," provided → Validation error"]}),`
`]}),`
`,e.jsx(n.h3,{children:"Creating a BYOC connection"}),`
`,e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`from airweave import AirweaveSDK
from airweave.types import OAuthBrowserAuthentication

airweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")

source_connection = airweave.source_connections.create(
    name="Notion connection (BYOC)",
    short_name="notion",
    readable_collection_id="my-collection-id",
    authentication=OAuthBrowserAuthentication(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        redirect_uri="https://your-app.com/callback"
    ),
    sync_immediately=False  # BYOC flows cannot sync immediately
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});

const sourceConnection = await airweave.sourceConnections.create({
    name: "Notion connection (BYOC)",
    shortName: "notion",
    readableCollectionId: "my-collection-id",
    authentication: {
        client_id: "YOUR_CLIENT_ID",
        client_secret: "YOUR_CLIENT_SECRET",
        redirect_uri: "https://your-app.com/callback"
    },
    syncImmediately: false  // BYOC flows cannot sync immediately
});
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST https://api.airweave.ai/source-connections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "Notion connection (BYOC)",
  "short_name": "notion",
  "readable_collection_id": "my-collection-id",
  "authentication": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uri": "https://your-app.com/callback"
  },
  "sync_immediately": false
}'
`})})]}),`
`,e.jsx(n.h2,{children:"OAuth Application Setup"}),`
`,e.jsx(n.h3,{children:"Required Redirect URIs"}),`
`,e.jsx(n.p,{children:"When setting up your OAuth application for BYOC, you'll need to add Airweave's callback URL as an allowed redirect URI:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`https://api.airweave.ai/oauth/callback
`})}),`
`,e.jsx(n.h3,{children:"Required Scopes"}),`
`,e.jsx(n.p,{children:"Each connector requires specific OAuth scopes to function properly. Check the individual connector documentation for the required scopes."}),`
`,e.jsx(n.h3,{children:"Example: GitHub OAuth Application Setup"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:"Go to GitHub Settings → Developer settings → OAuth Apps"}),`
`,e.jsx(n.li,{children:'Click "New OAuth App"'}),`
`,e.jsxs(n.li,{children:["Fill in the application details:",`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Application name"}),": Your application name"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Homepage URL"}),": Your application URL"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Authorization callback URL"}),": ",e.jsx(n.code,{children:"https://api.airweave.ai/oauth/callback"})]}),`
`]}),`
`]}),`
`,e.jsx(n.li,{children:"Note down the Client ID and Client Secret for use in your BYOC connection"}),`
`]}),`
`,e.jsx(n.h3,{children:"Getting Help"}),`
`,e.jsxs(n.p,{children:["If you encounter issues not covered in this documentation, please reach out to us at ",e.jsx(n.strong,{children:e.jsx(n.a,{href:"mailto:hello@airweave.ai",children:"hello@airweave.ai"})})," or check our ",e.jsx(n.a,{href:"/api-reference",children:"API Reference"})," for more detailed information about the OAuth endpoints."]})]})}function h(i={}){const{wrapper:n}={...s(),...i.components};return n?e.jsx(n,{...i,children:e.jsx(r,{...i})}):r(i)}function c(i,n){throw new Error("Expected component `"+i+"` to be defined: you likely forgot to import, pass, or provide it.")}export{h as default};
