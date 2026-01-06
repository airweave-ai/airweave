import{j as e}from"./main-BEToz-TC.js";import{u as o}from"./use-docs-content-ogu5VP42.js";function c(s){const n={a:"a",code:"code",h1:"h1",h2:"h2",h3:"h3",h4:"h4",hr:"hr",li:"li",ol:"ol",p:"p",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...o(),...s.components},{Accordion:t,Callout:r,Card:l}=n;return t||i("Accordion"),r||i("Callout"),l||i("Card"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"24px"},children:[e.jsx("img",{src:"icon.svg",alt:"Slack logo",width:"48",height:"48",className:"connector-icon"}),e.jsx("h1",{style:{margin:0},children:"Slack"})]}),`
`,e.jsx(n.h2,{children:"Configuration"}),`
`,e.jsx(n.p,{children:"Slack source connector using federated search."}),`
`,e.jsx(n.p,{children:`Instead of syncing all messages and files, this source searches Slack at query time
using the search.all API endpoint. This is necessary because Slack's rate limits
are too restrictive for full synchronization.`}),`
`,e.jsx(l,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/slack.py",children:e.jsx(n.p,{children:"Explore the Slack connector implementation"})}),`
`,e.jsx(n.h3,{children:"Authentication"}),`
`,e.jsxs(n.p,{children:["This connector uses ",e.jsx(n.strong,{children:"OAuth 2.0 authentication"}),". You can connect through the Airweave UI or API using the OAuth flow."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Supported authentication methods:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"OAuth Browser Flow (recommended for UI)"}),`
`,e.jsx(n.li,{children:"OAuth Token (for programmatic access)"}),`
`,e.jsx(n.li,{children:"Auth Provider (enterprise SSO)"}),`
`]}),`
`,e.jsx(n.h3,{children:"Configuration Options"}),`
`,e.jsx(n.p,{children:"This connector does not have any additional configuration options."}),`
`,e.jsx(n.h2,{children:"Data Models"}),`
`,e.jsx(n.p,{children:"The following data models are available for this connector:"}),`
`,e.jsxs(t,{title:"SlackMessageEntity",children:[e.jsx(n.p,{children:"Schema for Slack message entities from federated search."}),e.jsxs(n.p,{children:[`Reference:
`,e.jsx(n.a,{href:"https://api.slack.com/methods/search.messages",children:"https://api.slack.com/methods/search.messages"})]}),e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Field"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"text"}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"The text content of the message"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"user"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"User ID of the message author"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"username"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Username of the message author"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"ts"}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"Message timestamp (unique identifier)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"channel_id"}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"ID of the channel containing this message"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"channel_name"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Name of the channel"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"channel_is_private"}),e.jsx(n.td,{children:"Optional[bool]"}),e.jsx(n.td,{children:"Whether the channel is private"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"type"}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"Type of the message"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"permalink"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Permalink to the message in Slack"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"team"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Team/workspace ID"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"previous_message"}),e.jsx(n.td,{children:"Optional[Dict[str, Any]]"}),e.jsx(n.td,{children:"Previous message for context"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"next_message"}),e.jsx(n.td,{children:"Optional[Dict[str, Any]]"}),e.jsx(n.td,{children:"Next message for context"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"score"}),e.jsx(n.td,{children:"Optional[float]"}),e.jsx(n.td,{children:"Search relevance score from Slack"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"iid"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Internal search ID"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"url"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"URL to view the message in Slack"})]})]})]})]}),`
`,`
`,e.jsx(n.hr,{}),`
`,e.jsx(n.h1,{children:"Federated Search"}),`
`,e.jsxs(r,{intent:"info",children:[e.jsx(n.p,{children:e.jsx(n.strong,{children:"Real-Time Search Without Syncing"})}),e.jsxs(n.p,{children:["The Slack connector uses ",e.jsx(n.strong,{children:"federated search"})," to query your Slack workspace in real-time at search time, rather than syncing all messages into Airweave's database. This approach:"]}),e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Avoids hitting Slack's strict rate limits"}),`
`,e.jsx(n.li,{children:"Keeps your data in Slack (nothing synced to Airweave)"}),`
`,e.jsx(n.li,{children:"Returns fresh, up-to-date results at query time"}),`
`,e.jsx(n.li,{children:"Searches across all channels you have access to"}),`
`]}),e.jsx(n.p,{children:"When you search in Airweave, your query is automatically sent to Slack's search API, and results are merged with data from your other connected sources."})]}),`
`,e.jsx(n.h2,{children:"How It Works"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Connect your Slack workspace"})," using OAuth (one-time setup)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Search in Airweave"})," - your queries are automatically sent to Slack's search API in real-time"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Results are merged"})," with data from your other sources using intelligent ranking"]}),`
`]}),`
`,e.jsx(n.p,{children:"No data is synced or stored in Airweave - everything happens at search time."}),`
`,e.jsx(n.h2,{children:"Prerequisites"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Access to a Slack workspace where you have permissions to add apps"}),`
`,e.jsx(n.li,{children:"Administrator access to your Airweave instance"}),`
`]}),`
`,e.jsx(n.h2,{children:"Setup Steps"}),`
`,e.jsx(n.h3,{children:"Option A: Production Setup (OAuth Flow)"}),`
`,e.jsx(n.p,{children:"When running Airweave in production (non-localhost), simply:"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:"Navigate to your Airweave collection"}),`
`,e.jsx(n.li,{children:'Click "Add Source" and select "Slack"'}),`
`,e.jsx(n.li,{children:"Follow the OAuth flow to authorize Airweave"}),`
`,e.jsx(n.li,{children:"That's it! Your Slack workspace is now searchable"}),`
`]}),`
`,e.jsxs(n.p,{children:["The OAuth flow will request the ",e.jsx(n.code,{children:"search:read"})," user scope, which allows Airweave to search on your behalf."]}),`
`,e.jsx(n.h3,{children:"Option B: Local Development Setup (Manual Token)"}),`
`,e.jsxs(n.p,{children:["Slack does not allow OAuth2 flows for ",e.jsx(n.code,{children:"http://localhost"}),", so for local development you'll need to manually create a token."]}),`
`,e.jsx(n.h4,{children:"1. Create a Slack App"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:["Go to ",e.jsx(n.a,{href:"https://api.slack.com/apps",children:"https://api.slack.com/apps"})]}),`
`,e.jsx(n.li,{children:'Click the "Create New App" button'}),`
`,e.jsx(n.li,{children:'Choose "From scratch"'}),`
`,e.jsx(n.li,{children:'Enter a name for your app (e.g., "Airweave Local Dev")'}),`
`,e.jsx(n.li,{children:"Select the workspace you want to connect"}),`
`,e.jsx(n.li,{children:'Click "Create App"'}),`
`]}),`
`,e.jsx("img",{src:"create-app.png",alt:"Create app in Slack",width:"600"}),`
`,e.jsx(n.h4,{children:"2. Configure OAuth Permissions"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:'In your Slack app settings, navigate to "OAuth & Permissions" in the sidebar'}),`
`,e.jsx(n.li,{children:'Scroll down to the "Scopes" section'}),`
`,e.jsxs(n.li,{children:['Under "User Token Scopes", add the following scope:',`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"search:read"})," (required for federated search)"]}),`
`]}),`
`]}),`
`]}),`
`,e.jsx("img",{src:"user-token-scopes.png",alt:"User Token Scopes",width:"600"}),`
`,e.jsxs(r,{intent:"warning",children:[e.jsx(n.p,{children:e.jsx(n.strong,{children:"Scope Requirements"})}),e.jsxs(n.p,{children:["For federated search, you only need the ",e.jsx(n.code,{children:"search:read"})," user scope. This allows Airweave to search Slack on your behalf at query time."]}),e.jsxs(n.p,{children:["If you see scopes like ",e.jsx(n.code,{children:"channels:history"}),", ",e.jsx(n.code,{children:"channels:read"}),", ",e.jsx(n.code,{children:"users:read"})," in older documentation, those were for the legacy sync-based approach and are no longer needed."]})]}),`
`,e.jsx(n.h4,{children:"3. Install the App to Your Workspace"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:'Scroll back to the top of the "OAuth & Permissions" page'}),`
`,e.jsxs(n.li,{children:["Click the ",e.jsx(n.strong,{children:"Install to Workspace"})," button"]}),`
`,e.jsx(n.li,{children:'Review the permissions and click "Allow"'}),`
`,e.jsx(n.li,{children:"After installation, you'll be redirected back to the app settings"}),`
`,e.jsxs(n.li,{children:['Copy the "User OAuth Token" (it starts with ',e.jsx(n.code,{children:"xoxp-"}),")"]}),`
`]}),`
`,e.jsx("img",{src:"oauth2-token.png",alt:"OAuth2 User token in Slack",width:"600"}),`
`,e.jsx(n.h4,{children:"4. Add the Token to Airweave"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:"In your Airweave application, navigate to the integrations section"}),`
`,e.jsx(n.li,{children:'Select "Slack" from the available integrations'}),`
`,e.jsx(n.li,{children:'Choose "Direct Token Injection"'}),`
`,e.jsx(n.li,{children:"Paste the User OAuth Token you copied in the previous step"}),`
`,e.jsx(n.li,{children:"Save your changes"}),`
`]}),`
`,e.jsx("img",{src:"add-token-in-airweave.png",alt:"Add Slack token in Airweave",width:"600"}),`
`,e.jsx(n.h2,{children:"Verification"}),`
`,e.jsx(n.p,{children:"After completing these steps, try searching in your Airweave collection. Your search query will be automatically sent to Slack, and relevant messages will appear in your search results alongside data from your other sources."}),`
`,e.jsx(n.h2,{children:"Troubleshooting"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"No Slack results appearing"}),": Verify the token was copied correctly and hasn't expired"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Permission errors"}),": Ensure you've added the ",e.jsx(n.code,{children:"search:read"})," user scope to your Slack app"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Authentication failed"}),": Try regenerating the token in Slack and updating it in Airweave"]}),`
`]})]})}function d(s={}){const{wrapper:n}={...o(),...s.components};return n?e.jsx(n,{...s,children:e.jsx(c,{...s})}):c(s)}function i(s,n){throw new Error("Expected component `"+s+"` to be defined: you likely forgot to import, pass, or provide it.")}export{d as default};
