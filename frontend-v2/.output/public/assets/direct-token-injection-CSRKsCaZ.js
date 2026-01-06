import{j as e}from"./main-BEToz-TC.js";import{u as s}from"./use-docs-content-ogu5VP42.js";function t(o){const n={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",ul:"ul",...s(),...o.components},{CodeBlocks:i,Note:a}=n;return i||r("CodeBlocks"),a||r("Note"),e.jsxs(e.Fragment,{children:[e.jsx(n.h2,{children:"Use case"}),`
`,e.jsx(n.p,{children:`If you embed Airweave inside your own product you might already manage OAuth 2.0 tokens for your users.
In that case, you do not want to have to ask them to click through a second consent screen for Airweave.
Airweave therefore allows you to provide existing tokens to Airweave directly, so that`}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Your service owns token storage and rotation."}),`
`,e.jsx(n.li,{children:"Airweave consumes the tokens solely for data sync."}),`
`,e.jsx(n.li,{children:"No additional user interaction required."}),`
`]}),`
`,e.jsx(n.p,{children:"There are two common scenarios:"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Create a new source connection"})," by sending the access token."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Trigger a sync"})," on an existing source connection using stored credentials."]}),`
`]}),`
`,e.jsx(n.p,{children:"The next sections walk you through both flows."}),`
`,e.jsx(n.h2,{children:"Create a source connection with your own tokens"}),`
`,e.jsxs(n.p,{children:["Skip the OAuth 2.0 flow entirely by sending your own tokens in the ",e.jsx(n.code,{children:"POST /source-connections"})," call. You are responsible for acquiring and storing these tokens, Airweave simply uses what you provide."]}),`
`,e.jsx(n.p,{children:"Creating a source connection with direct tokens looks like this:"}),`
`,e.jsxs(i,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`from airweave import AirweaveSDK
from airweave.types import OAuthTokenAuthentication

airweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")

source_connection = airweave.source_connections.create(
    name="Asana connection",
    short_name="asana",
    readable_collection_id="my-collection-id",
    authentication=OAuthTokenAuthentication(
        access_token="YOUR_ACCESS_TOKEN",
    ),
    sync_immediately=True
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});

const sourceConnection = await airweave.sourceConnections.create({
    name: "Asana connection",
    shortName: "asana",
    readableCollectionId: "my-collection-id",
    authentication: {
        type: "oauth_token",
        accessToken: "YOUR_ACCESS_TOKEN",
        refreshToken: "YOUR_REFRESH_TOKEN"  // Optional
    },
    syncImmediately: true
});
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST https://api.airweave.ai/source-connections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "Asana connection",
  "short_name": "asana",
  "readable_collection_id": "my-collection-id",
  "authentication": {
    "type": "oauth_token",
    "access_token": "YOUR_ACCESS_TOKEN",
    "refresh_token": "YOUR_REFRESH_TOKEN"
  },
  "sync_immediately": true
}'
`})})]}),`
`,e.jsx(n.h2,{children:"Trigger a sync"}),`
`,e.jsxs(n.p,{children:[e.jsxs(a,{children:["The run endpoint uses the stored credentials from the source connection. To use different credentials, create a new source connection with ",e.jsx(n.code,{children:"OAuthTokenAuthentication"}),"."]}),`
By default, Airweave uses the credentials obtained during the initial OAuth 2.0 handshake to run a data synchronization job.`]}),`
`,e.jsx(n.p,{children:"Here is an example:"}),`
`,e.jsxs(i,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`from airweave import AirweaveSDK

airweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")

job = airweave.source_connections.run(
    source_connection_id="source_connection_id"
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});

const job = await airweave.sourceConnections.run(
    "source_connection_id"
);
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST https://api.airweave.ai/source-connections/source_connection_id/run \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json"
`})})]}),`
`,e.jsx(n.h3,{children:"Auth provider connections"}),`
`,e.jsxs(n.p,{children:["Airweave also supports creating source connections through auth providers like Composio and Pipedream. Check out the ",e.jsx(n.a,{href:"/auth-providers",children:"Authentication Providers documentation"})," to learn more."]}),`
`,e.jsxs(n.p,{children:["If you have an edge case that isn't covered by these features, please let us know at ",e.jsx(n.strong,{children:e.jsx(n.a,{href:"mailto:hello@airweave.ai",children:"hello@airweave.ai"})}),"."]})]})}function h(o={}){const{wrapper:n}={...s(),...o.components};return n?e.jsx(n,{...o,children:e.jsx(t,{...o})}):t(o)}function r(o,n){throw new Error("Expected component `"+o+"` to be defined: you likely forgot to import, pass, or provide it.")}export{h as default};
