import{j as e}from"./main-BEToz-TC.js";import{u as d}from"./use-docs-content-ogu5VP42.js";function l(a){const n={a:"a",code:"code",p:"p",pre:"pre",...d(),...a.components},{Card:i,CardGroup:s,CodeBlocks:t,Step:r,Steps:c}=n;return i||o("Card"),s||o("CardGroup"),t||o("CodeBlocks"),r||o("Step"),c||o("Steps"),e.jsxs(e.Fragment,{children:[e.jsx(n.p,{children:"Follow this guide to get up and running with Airweave in just a few steps."}),`
`,e.jsxs(c,{children:[e.jsxs(r,{title:"Choose your deployment",toc:!0,children:[e.jsxs(n.p,{children:["The simplest way to use Airweave is through our hosted cloud platform at ",e.jsx(n.a,{href:"https://app.airweave.ai",children:"app.airweave.ai"}),"."]}),e.jsxs(n.p,{children:["If you prefer to run Airweave yourself, you can deploy it locally on macOS, Linux or WSL. After cloning the repository and starting the server, you will be able to open the dashboard at ",e.jsx(n.a,{href:"http://localhost:8080",children:"http://localhost:8080"})]}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`git clone https://github.com/airweave-ai/airweave.git
cd airweave
./start.sh
`})})]}),e.jsxs(r,{title:"Set-up Airweave client",toc:!0,children:[e.jsx(n.p,{children:"Airweave provides SDKs for Python and Node.js. Install the package."}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`pip install airweave-sdk
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`npm install @airweave/sdk
`})})]}),e.jsx(n.p,{children:"Now, create and copy your API key from your Airweave dashboard."}),e.jsx("video",{src:"./airweave_api_key.mp4",controls:!0,loop:!0,autoplay:!0,muted:!0,playsinline:!0,style:{aspectRatio:"16 / 9",width:"100%"},children:e.jsx(n.p,{children:"Your browser does not support the video tag."})}),e.jsxs(n.p,{children:["Initialize the Airweave client with your new API key. For local deployments, set base_url to ",e.jsx(n.code,{children:'"http://localhost:8001"'}),"."]}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`from airweave import AirweaveSDK

airweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", base_url: "https://api.airweave.ai"});
`})})]})]}),e.jsxs(r,{title:"Create a collection",toc:!0,children:[e.jsx(n.p,{children:"A collection is a group of different data sources that you can search using a single endpoint."}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`collection = airweave.collections.create(name="My First Collection")

print(f"Created collection: {collection.readable_id}")
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:'const collection = await airweave.collections.create({name: "My First Collection"});\n\nconsole.log(`Created collection: ${collection.readable_id}`);\n'})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "name": "My First Collection"
  }'
`})})]})]}),e.jsxs(r,{title:"Add source connection(s) to your collection",toc:!0,children:[e.jsx(n.p,{children:"A source connection links a specific app or database to your collection. It handles authentication and automatically syncs data."}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`source_connection = airweave.source_connections.create(
    name="My Stripe Connection",
    short_name="stripe",
    readable_collection_id=collection.readable_id,
    authentication={
        "credentials": {
            "api_key": "your_stripe_api_key"  # Replace with real API key
        }
    }
)

print(f"Status: {source_connection.status}")
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const sourceConnection = await airweave.sourceConnections.create({
  name: "My Stripe Connection",
  short_name: "stripe",
  readable_collection_id: collection.readable_id,
  authentication: {
    credentials: {
      api_key: "SK_TEST_YOUR_STRIPE_API_KEY"
    }
  }
});

console.log(\`Status: \${sourceConnection.status}\`);
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/source-connections' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "name": "My Stripe Connection",
    "short_name": "stripe",
    "readable_collection_id": "my-first-collection-abc123",
    "authentication": {
      "credentials": {
        "api_key": "SK_TEST_YOUR_STRIPE_API_KEY"
      }
    }
  }'
`})})]})]}),e.jsxs(r,{title:"Search your collection",toc:!0,children:[e.jsx(n.p,{children:"You can now search your collection and get the most relevant results from all connected sources."}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-Python",children:`results = airweave.collections.search(
    readable_id=collection.readable_id,
    query="Find returned payments from user John Doe?",
)

for result in results.results:
  print(result)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const results = await airweave.collections.search(
  collection.readable_id,
  { query: "Find returned payments from user John Doe?" }
);

results.results.forEach(result => {
  console.log(result);
});
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X GET 'https://api.airweave.ai/collections/my-first-collection-abc123/search?query=Find%20returned%20payments%20from%20user%20John%20Doe%3F' \\
  -H 'x-api-key: YOUR_API_KEY'
`})})]})]})]}),`
`,e.jsx(n.p,{children:"You've now successfully deployed Airweave, connected your first data source, and searched your first collection. To continue, you can explore more integrations and dive into the API reference. For community and support, check out the links below."}),`
`,e.jsxs(s,{cols:2,children:[e.jsxs(i,{title:"GitHub Repository",icon:"fa-brands fa-github",href:"https://github.com/airweave-ai/airweave",children:[e.jsx(n.p,{children:"Join our growing open-source community."}),e.jsx(n.p,{children:"View code, contribute, and report issues."})]}),e.jsxs(i,{title:"Community Support",icon:"fa-brands fa-discord",href:"https://discord.gg/484HY9Ehxt",children:[e.jsx(n.p,{children:"Get help from our team and community."}),e.jsx(n.p,{children:"Share feedback and feature requests."})]})]})]})}function u(a={}){const{wrapper:n}={...d(),...a.components};return n?e.jsx(n,{...a,children:e.jsx(l,{...a})}):l(a)}function o(a,n){throw new Error("Expected component `"+a+"` to be defined: you likely forgot to import, pass, or provide it.")}export{u as default};
