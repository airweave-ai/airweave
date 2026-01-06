import{j as e}from"./main-BEToz-TC.js";import{u as o}from"./use-docs-content-ogu5VP42.js";function a(n){const t={code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",...o(),...n.components},{Card:i,ParamField:r}=t;return i||s("Card"),r||s("ParamField"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",children:[e.jsx("img",{src:"icon.svg",alt:"Sqlite logo",width:"72",height:"72",className:"connector-icon"}),e.jsxs("div",{className:"connector-info",children:[e.jsx("h1",{children:"Sqlite"}),e.jsx("p",{children:"Connect your Sqlite data to Airweave"})]})]}),`
`,e.jsx(t.h2,{children:"Overview"}),`
`,e.jsx(t.p,{children:"The Sqlite connector allows you to sync data from Sqlite into Airweave, making it available for search and retrieval by your agents."}),`
`,e.jsx(t.h2,{children:"Configuration"}),`
`,e.jsx(t.h3,{children:"SQLiteSource"}),`
`,e.jsx(t.p,{children:"SQLite source implementation."}),`
`,e.jsx(t.p,{children:`This source connects to a SQLite database and generates entities for each table.
It uses database introspection to:`}),`
`,e.jsxs(t.ol,{children:[`
`,e.jsx(t.li,{children:"Discover tables and their structures"}),`
`,e.jsx(t.li,{children:"Create appropriate entity classes dynamically"}),`
`,e.jsx(t.li,{children:"Generate entities for each table's data"}),`
`]}),`
`,e.jsx(i,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/sqlite.py",children:e.jsx(t.p,{children:"Explore the Sqlite connector implementation"})}),`
`,e.jsx(t.h3,{children:"Authentication"}),`
`,e.jsxs(t.p,{children:["This connector uses a custom authentication configuration class: ",e.jsx(t.code,{children:"SQLiteAuthConfig"}),"."]}),`
`,e.jsxs(i,{title:"Authentication Configuration",className:"auth-config-card",style:{backgroundColor:"rgba(0, 0, 0, 0.1)",padding:"16px",marginBottom:"24px"},children:[e.jsx(t.p,{children:"SQLite authentication configuration."}),e.jsx(r,{path:"host",type:"str",required:!0,children:e.jsx(t.p,{children:"The host of the SQLite database"})}),e.jsx(r,{path:"port",type:"int",required:!0,children:e.jsx(t.p,{children:"The port of the SQLite database"})}),e.jsx(r,{path:"database",type:"str",required:!0,children:e.jsx(t.p,{children:"The name of the SQLite database"})}),e.jsx(r,{path:"user",type:"str",required:!0,children:e.jsx(t.p,{children:"The username for the SQLite database"})}),e.jsx(r,{path:"password",type:"str",required:!0,children:e.jsx(t.p,{children:"The password for the SQLite database"})}),e.jsx(r,{path:"schema",type:"str",required:!1,default:"public",children:e.jsx(t.p,{children:"The schema of the SQLite database"})}),e.jsx(r,{path:"tables",type:"str",required:!1,default:"*",children:e.jsx(t.p,{children:"Comma separated list of tables to sync. For example, 'users,orders'. For all tables, use '*'"})})]}),`
`]})}function h(n={}){const{wrapper:t}={...o(),...n.components};return t?e.jsx(t,{...n,children:e.jsx(a,{...n})}):a(n)}function s(n,t){throw new Error("Expected component `"+n+"` to be defined: you likely forgot to import, pass, or provide it.")}export{h as default};
