import{j as e}from"./main-BEToz-TC.js";import{u as c}from"./use-docs-content-ogu5VP42.js";function l(r){const n={a:"a",blockquote:"blockquote",code:"code",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",ul:"ul",...c(),...r.components},{Tab:s,Tabs:i}=n;return s||t("Tab"),i||t("Tabs"),e.jsxs(e.Fragment,{children:[e.jsx(n.h3,{children:"Prerequisites"}),`
`,e.jsx(n.p,{children:"Before you start you’ll need:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"A collection with data"}),": at least one source connection must have completed its initial sync. See the ",e.jsx(n.a,{href:"https://docs.airweave.ai/quickstart",children:"Quickstart"})," if you need to set this up."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"An API key"}),": Create one in the Airweave dashboard under ",e.jsx(n.strong,{children:"API Keys"}),"."]}),`
`]}),`
`,e.jsx(n.h3,{children:"Set-up"}),`
`,e.jsxs(i,{children:[e.jsxs(s,{title:"Cursor",children:[e.jsxs(n.blockquote,{children:[`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Requirement"}),": Cursor version 0.45.6 or later"]}),`
`]}),e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:["Open ",e.jsx(n.strong,{children:"Cursor Settings"})]}),`
`,e.jsxs(n.li,{children:["Go to ",e.jsx(n.strong,{children:"Features > MCP Servers"})]}),`
`,e.jsxs(n.li,{children:["Click ",e.jsx(n.strong,{children:'"+ Add new global MCP server"'})]}),`
`,e.jsx(n.li,{children:"Add this configuration:"}),`
`]}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-json",children:`{
  "mcpServers": {
    "airweave-search": {
      "command": "npx",
      "args": ["-y", "airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "your-api-key",
        "AIRWEAVE_COLLECTION": "your-collection-id"
      }
    }
  }
}
`})})]}),e.jsxs(s,{title:"Claude Desktop",children:[e.jsx(n.p,{children:`Add the following to your Claude Desktop config file and restart Claude Desktop afterwards.
After a restart the search tool will appear in Claude’s composer.`}),e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"macOS/Linux"}),": ",e.jsx(n.code,{children:"~/.claude/claude_desktop_config.json"})]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Windows"}),": ",e.jsx(n.code,{children:"%APPDATA%\\claude\\claude_desktop_config.json"})]}),`
`]}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-json",children:`{
  "mcpServers": {
    "airweave-search": {
      "command": "npx",
      "args": ["-y", "airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "your-api-key",
        "AIRWEAVE_COLLECTION": "your-collection-id"
      }
    }
  }
}
`})})]}),e.jsxs(s,{title:"VS Code",children:[e.jsxs(n.p,{children:["Add to your User Settings (JSON) via ",e.jsx(n.strong,{children:"Ctrl+Shift+P"})," → ",e.jsx(n.strong,{children:'"Preferences: Open User Settings (JSON)"'}),":"]}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-json",children:`{
  "mcp": {
    "inputs": [
      {
        "type": "promptString",
        "id": "airweaveApiKey",
        "description": "Airweave API Key",
        "password": true
      },
      {
        "type": "promptString",
        "id": "airweaveCollection",
        "description": "Airweave Collection ID"
      }
    ],
    "servers": {
      "airweave": {
        "command": "npx",
        "args": ["-y", "airweave-mcp-search"],
        "env": {
          "AIRWEAVE_API_KEY": "\${input:airweaveApiKey}",
          "AIRWEAVE_COLLECTION": "\${input:airweaveCollection}"
        }
      }
    }
  }
}
`})})]})]}),`
`,e.jsx(n.p,{children:"These environment variables can be set:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"AIRWEAVE_API_KEY"})," (Required): Authenticates the MCP server with the Airweave API so it can run searches on your behalf."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"AIRWEAVE_COLLECTION"})," (Required): Readable ID of the collection to query. All ",e.jsx(n.code,{children:"search"})," calls are scoped to this collection."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"AIRWEAVE_BASE_URL"})," (Optional): Override if you're running a self-hosted Airweave instance (default: ",e.jsx(n.code,{children:"https://api.airweave.ai"}),")."]}),`
`]}),`
`,e.jsx(n.h3,{children:"Available tools"}),`
`,e.jsx(n.p,{children:"The MCP server provides two tools:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"search"}),": Enhanced search across all source connections in the collection with full parameter control and optional AI completion."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"get-config"}),": View current configuration and connection status so you can verify everything is working correctly. No parameters required."]}),`
`]}),`
`,e.jsx(n.h3,{children:"Advanced Search Features"}),`
`,e.jsxs(n.p,{children:["The search tool uses the ",e.jsx(n.strong,{children:"POST"})," endpoint for full control over search parameters."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Available Parameters:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"retrieval_strategy"}),": Choose between 'hybrid', 'neural', or 'keyword' search (default: 'hybrid')"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"expand_query"}),": Generate query variations for better recall (default: true)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"interpret_filters"}),": Extract filters from natural language (default: false)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"rerank"}),": LLM-based result reranking for improved relevance (default: true)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"generate_answer"}),": AI-generated completion from results (default: true)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"temporal_relevance"}),": Recency weighting from 0.0 to 1.0 (default: 0.3)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"limit"}),": Maximum number of results (default: 1000)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"offset"}),": Pagination offset (default: 0)"]}),`
`]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Natural Language Examples:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:['"Use neural search for semantic similarity" → ',e.jsx(n.code,{children:'retrieval_strategy: "neural"'})]}),`
`,e.jsxs(n.li,{children:['"Search without expanding the query" → ',e.jsx(n.code,{children:"expand_query: false"})]}),`
`,e.jsxs(n.li,{children:['"Extract filters from my query" → ',e.jsx(n.code,{children:"interpret_filters: true"})]}),`
`,e.jsxs(n.li,{children:['"Disable reranking for faster results" → ',e.jsx(n.code,{children:"rerank: false"})]}),`
`,e.jsxs(n.li,{children:['"Just return results, no AI summary" → ',e.jsx(n.code,{children:"generate_answer: false"})]}),`
`,e.jsxs(n.li,{children:['"Prioritize recent documents" → ',e.jsx(n.code,{children:"temporal_relevance: 0.8"})]}),`
`]})]})}function d(r={}){const{wrapper:n}={...c(),...r.components};return n?e.jsx(n,{...r,children:e.jsx(l,{...r})}):l(r)}function t(r,n){throw new Error("Expected component `"+r+"` to be defined: you likely forgot to import, pass, or provide it.")}export{d as default};
