import{j as e}from"./main-BEToz-TC.js";import{u as c}from"./use-docs-content-ogu5VP42.js";function i(r){const t={a:"a",h2:"h2",h3:"h3",li:"li",p:"p",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...c(),...r.components},{Accordion:s,Card:n}=t;return s||o("Accordion"),n||o("Card"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"24px"},children:[e.jsx("img",{src:"icon.svg",alt:"Jira logo",width:"48",height:"48",className:"connector-icon"}),e.jsx("h1",{style:{margin:0},children:"Jira"})]}),`
`,e.jsx(t.h2,{children:"Configuration"}),`
`,e.jsx(t.p,{children:"Jira source connector integrates with the Jira REST API to extract project management data."}),`
`,e.jsx(t.p,{children:"Connects to your Jira Cloud instance."}),`
`,e.jsx(t.p,{children:`It provides comprehensive access to projects, issues, and their
relationships for agile development and issue tracking workflows.`}),`
`,e.jsx(n,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/jira.py",children:e.jsx(t.p,{children:"Explore the Jira connector implementation"})}),`
`,e.jsx(t.h3,{children:"Authentication"}),`
`,e.jsxs(t.p,{children:["This connector uses ",e.jsx(t.strong,{children:"OAuth 2.0 authentication"}),". You can connect through the Airweave UI or API using the OAuth flow."]}),`
`,e.jsx(t.p,{children:e.jsx(t.strong,{children:"Supported authentication methods:"})}),`
`,e.jsxs(t.ul,{children:[`
`,e.jsx(t.li,{children:"OAuth Browser Flow (recommended for UI)"}),`
`,e.jsx(t.li,{children:"OAuth Token (for programmatic access)"}),`
`,e.jsx(t.li,{children:"Auth Provider (enterprise SSO)"}),`
`]}),`
`,e.jsx(t.h3,{children:"Configuration Options"}),`
`,e.jsx(t.p,{children:"This connector does not have any additional configuration options."}),`
`,e.jsx(t.h2,{children:"Data Models"}),`
`,e.jsx(t.p,{children:"The following data models are available for this connector:"}),`
`,e.jsxs(s,{title:"JiraProjectEntity",children:[e.jsx(t.p,{children:"Schema for a Jira Project."}),e.jsxs(t.p,{children:[`Reference:
`,e.jsx(t.a,{href:"https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/",children:"https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/"})]}),e.jsxs(t.table,{children:[e.jsx(t.thead,{children:e.jsxs(t.tr,{children:[e.jsx(t.th,{children:"Field"}),e.jsx(t.th,{children:"Type"}),e.jsx(t.th,{children:"Description"})]})}),e.jsxs(t.tbody,{children:[e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"project_key"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"Unique key of the project (e.g., 'PROJ')."})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"description"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Description of the project."})]})]})]})]}),`
`,e.jsxs(s,{title:"JiraIssueEntity",children:[e.jsx(t.p,{children:"Schema for a Jira Issue."}),e.jsxs(t.p,{children:[`Reference:
`,e.jsx(t.a,{href:"https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/",children:"https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/"})]}),e.jsxs(t.table,{children:[e.jsx(t.thead,{children:e.jsxs(t.tr,{children:[e.jsx(t.th,{children:"Field"}),e.jsx(t.th,{children:"Type"}),e.jsx(t.th,{children:"Description"})]})}),e.jsxs(t.tbody,{children:[e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"issue_key"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"Jira key for the issue (e.g. 'PROJ-123')."})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"summary"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Short summary field of the issue."})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"description"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Detailed description of the issue."})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"status"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Current workflow status of the issue."})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"issue_type"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Type of the issue (bug, task, story, etc.)."})]})]})]})]}),`
`]})}function l(r={}){const{wrapper:t}={...c(),...r.components};return t?e.jsx(t,{...r,children:e.jsx(i,{...r})}):i(r)}function o(r,t){throw new Error("Expected component `"+r+"` to be defined: you likely forgot to import, pass, or provide it.")}export{l as default};
