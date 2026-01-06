import{j as e}from"./main-BEToz-TC.js";import{u as r}from"./use-docs-content-ogu5VP42.js";function i(s){const n={h2:"h2",li:"li",p:"p",strong:"strong",ul:"ul",...r(),...s.components},{Icon:o}=n;return o||c("Icon"),e.jsxs(e.Fragment,{children:[e.jsx(n.p,{children:"Airweave connects to your apps, databases, and documents, then turns them into knowledge you can search. To understand how it works, you only need a few core concepts."}),`
`,e.jsxs(n.h2,{children:[e.jsx(o,{icon:"fa-solid fa-database",size:"5",color:"#4199D3"})," Source"]}),`
`,e.jsxs(n.p,{children:["A ",e.jsx(n.strong,{children:"Source"})," is a specific application, database, or workspace that Airweave has a connector for. Sources are the external systems where your data lives."]}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Examples:"})," Zendesk, GitHub, Google Drive, Notion, PostgreSQL, Stripe"]}),`
`,e.jsxs(n.h2,{children:[e.jsx(o,{icon:"fa-solid fa-plug",size:"5",color:"#4199D3"})," Connector"]}),`
`,e.jsxs(n.p,{children:["A ",e.jsx(n.strong,{children:"Connector"})," is the integration that Airweave provides for a source. It defines what data types can be synced, how authentication works, and the specific entities that can be extracted."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Examples:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Zendesk connector (for tickets, users, organizations)"}),`
`,e.jsx(n.li,{children:"GitHub connector (for repositories, issues, pull requests)"}),`
`,e.jsx(n.li,{children:"Google Drive connector (for documents, folders, comments)"}),`
`]}),`
`,e.jsxs(n.h2,{children:[e.jsx(o,{icon:"fa-solid fa-link",size:"5",color:"#4199D3"})," Source Connection"]}),`
`,e.jsxs(n.p,{children:["A ",e.jsx(n.strong,{children:"Source Connection"})," is a live connection created from a connector between Airweave and a specific source using your credentials. In that sense, each connection represents an authenticated and synced instance of connection between Airweave and a source."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Examples:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"A live connection between Airweave and a Zendesk workspace"}),`
`,e.jsx(n.li,{children:"A live connection between Airweave and a specific GitHub repository"}),`
`]}),`
`,e.jsxs(n.h2,{children:[e.jsx(o,{icon:"fa-solid fa-file-alt",size:"5",color:"#4199D3"})," Entity"]}),`
`,e.jsxs(n.p,{children:["An ",e.jsx(n.strong,{children:"Entity"})," is an individual data item pulled from a source. These are the actual pieces of data that get synced and made searchable."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Examples:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"A Zendesk ticket or message"}),`
`,e.jsx(n.li,{children:"A GitHub issue or pull request"}),`
`,e.jsx(n.li,{children:"A Google Doc or spreadsheet"}),`
`,e.jsx(n.li,{children:"A database table row"}),`
`]}),`
`,e.jsxs(n.h2,{children:[e.jsx(o,{icon:"fa-solid fa-layer-group",size:"5",color:"#4199D3"})," Collection"]}),`
`,e.jsxs(n.p,{children:["A ",e.jsx(n.strong,{children:"Collection"})," is a searchable knowledge base made up of synced data from one or more source connections. When you search a collection, queries run across all entities from all its connected sources."]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Key features:"})}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Unified search interface across multiple sources"}),`
`,e.jsx(n.li,{children:"Vector embeddings for semantic search"}),`
`,e.jsx(n.li,{children:"Real-time data synchronization"}),`
`,e.jsx(n.li,{children:"Configurable search parameters and filters"}),`
`]})]})}function l(s={}){const{wrapper:n}={...r(),...s.components};return n?e.jsx(n,{...s,children:e.jsx(i,{...s})}):i(s)}function c(s,n){throw new Error("Expected component `"+s+"` to be defined: you likely forgot to import, pass, or provide it.")}export{l as default};
