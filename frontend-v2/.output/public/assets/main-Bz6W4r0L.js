import{j as e}from"./main-BEToz-TC.js";import{u as o}from"./use-docs-content-ogu5VP42.js";function a(t){const r={code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",...o(),...t.components},{Card:s,ParamField:n}=r;return s||i("Card"),n||i("ParamField"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",children:[e.jsx("img",{src:"icon.svg",alt:"Sql Server logo",width:"72",height:"72",className:"connector-icon"}),e.jsxs("div",{className:"connector-info",children:[e.jsx("h1",{children:"Sql Server"}),e.jsx("p",{children:"Connect your Sql Server data to Airweave"})]})]}),`
`,e.jsx(r.h2,{children:"Overview"}),`
`,e.jsx(r.p,{children:"The Sql Server connector allows you to sync data from Sql Server into Airweave, making it available for search and retrieval by your agents."}),`
`,e.jsx(r.h2,{children:"Configuration"}),`
`,e.jsx(r.h3,{children:"SQLServerSource"}),`
`,e.jsx(r.p,{children:"SQL Server source implementation."}),`
`,e.jsx(r.p,{children:`This source connects to a SQL Server database and generates entities for each table
in the specified schemas. It uses database introspection to:`}),`
`,e.jsxs(r.ol,{children:[`
`,e.jsx(r.li,{children:"Discover tables and their structures"}),`
`,e.jsx(r.li,{children:"Create appropriate entity classes dynamically"}),`
`,e.jsx(r.li,{children:"Generate entities for each table's data"}),`
`]}),`
`,e.jsx(s,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/sql_server.py",children:e.jsx(r.p,{children:"Explore the Sql Server connector implementation"})}),`
`,e.jsx(r.h3,{children:"Authentication"}),`
`,e.jsxs(r.p,{children:["This connector uses a custom authentication configuration class: ",e.jsx(r.code,{children:"SQLServerAuthConfig"}),"."]}),`
`,e.jsxs(s,{title:"Authentication Configuration",className:"auth-config-card",style:{backgroundColor:"rgba(0, 0, 0, 0.1)",padding:"16px",marginBottom:"24px"},children:[e.jsx(r.p,{children:"SQL Server authentication configuration."}),e.jsx(n,{path:"host",type:"str",required:!0,children:e.jsx(r.p,{children:"The host of the SQLServer database"})}),e.jsx(n,{path:"port",type:"int",required:!0,children:e.jsx(r.p,{children:"The port of the SQLServer database"})}),e.jsx(n,{path:"database",type:"str",required:!0,children:e.jsx(r.p,{children:"The name of the SQLServer database"})}),e.jsx(n,{path:"user",type:"str",required:!0,children:e.jsx(r.p,{children:"The username for the SQLServer database"})}),e.jsx(n,{path:"password",type:"str",required:!0,children:e.jsx(r.p,{children:"The password for the SQLServer database"})}),e.jsx(n,{path:"schema",type:"str",required:!1,default:"public",children:e.jsx(r.p,{children:"The schema of the SQLServer database"})}),e.jsx(n,{path:"tables",type:"str",required:!1,default:"*",children:e.jsx(r.p,{children:"Comma separated list of tables to sync. For example, 'users,orders'. For all tables, use '*'"})})]}),`
`]})}function h(t={}){const{wrapper:r}={...o(),...t.components};return r?e.jsx(r,{...t,children:e.jsx(a,{...t})}):a(t)}function i(t,r){throw new Error("Expected component `"+t+"` to be defined: you likely forgot to import, pass, or provide it.")}export{h as default};
