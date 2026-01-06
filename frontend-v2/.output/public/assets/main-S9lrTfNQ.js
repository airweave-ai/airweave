import{j as t}from"./main-BEToz-TC.js";import{u as c}from"./use-docs-content-ogu5VP42.js";function l(i){const e={h2:"h2",h3:"h3",p:"p",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",...c(),...i.components},{Accordion:s,Card:r,ParamField:n}=e;return s||a("Accordion"),r||a("Card"),n||a("ParamField"),t.jsxs(t.Fragment,{children:[`
`,t.jsxs("div",{className:"connector-header",style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"24px"},children:[t.jsx("img",{src:"icon.svg",alt:"Ctti logo",width:"48",height:"48",className:"connector-icon"}),t.jsx("h1",{style:{margin:0},children:"Ctti"})]}),`
`,t.jsx(e.h2,{children:"Configuration"}),`
`,t.jsx(e.p,{children:"CTTI source connector integrates with the AACT PostgreSQL database to extract trials."}),`
`,t.jsx(e.p,{children:"Connects to the Aggregate Analysis of ClinicalTrials.gov database."}),`
`,t.jsx(e.p,{children:`It creates web entities that link to
ClinicalTrials.gov pages.`}),`
`,t.jsx(r,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/ctti.py",children:t.jsx(e.p,{children:"Explore the Ctti connector implementation"})}),`
`,t.jsx(e.h3,{children:"Authentication"}),`
`,t.jsx(e.p,{children:"This connector uses a custom authentication configuration."}),`
`,t.jsxs(r,{title:"Authentication Configuration",className:"auth-config-card",style:{backgroundColor:"rgba(0, 0, 0, 0.1)",padding:"16px",marginBottom:"24px"},children:[t.jsx(e.p,{children:"CTTI Clinical Trials authentication credentials schema."}),t.jsx(n,{path:"username",type:"str",required:!0,children:t.jsx(e.p,{children:"Username for the AACT Clinical Trials database"})}),t.jsx(n,{path:"password",type:"str",required:!0,children:t.jsx(e.p,{children:"Password for the AACT Clinical Trials database"})})]}),`
`,t.jsx(e.h3,{children:"Configuration Options"}),`
`,t.jsx(e.p,{children:"The following configuration options are available for this connector:"}),`
`,t.jsxs(r,{title:"Configuration Parameters",className:"config-card",style:{backgroundColor:"rgba(0, 0, 0, 0.05)",padding:"16px",marginBottom:"24px"},children:[t.jsx(e.p,{children:"CTTI AACT configuration schema."}),t.jsx(n,{path:"limit",type:"int",required:!1,default:1e4,children:t.jsx(e.p,{children:"Maximum number of clinical trial studies to fetch from AACT database"})}),t.jsx(n,{path:"skip",type:"int",required:!1,default:0,children:t.jsx(e.p,{children:"Number of clinical trial studies to skip (for pagination). Use with limit to fetch different batches."})})]}),`
`,t.jsx(e.h2,{children:"Data Models"}),`
`,t.jsx(e.p,{children:"The following data models are available for this connector:"}),`
`,t.jsxs(s,{title:"CTTIWebEntity",children:[t.jsx(e.p,{children:"Web entity for CTTI clinical trials."}),t.jsx(e.p,{children:`Represents a clinical trial study from ClinicalTrials.gov with an NCT ID.
"WebFileEntity",
"WebFileEntity",
This entity will be processed by the web_fetcher transformer to download
the actual clinical trial content from ClinicalTrials.gov.`}),t.jsxs(e.table,{children:[t.jsx(e.thead,{children:t.jsxs(e.tr,{children:[t.jsx(e.th,{children:"Field"}),t.jsx(e.th,{children:"Type"}),t.jsx(e.th,{children:"Description"})]})}),t.jsxs(e.tbody,{children:[t.jsxs(e.tr,{children:[t.jsx(e.td,{children:"nct_id"}),t.jsx(e.td,{children:"str"}),t.jsx(e.td,{children:"The NCT ID of the clinical trial study"})]}),t.jsxs(e.tr,{children:[t.jsx(e.td,{children:"study_url"}),t.jsx(e.td,{children:"str"}),t.jsx(e.td,{children:"The full URL to the clinical trial study on ClinicalTrials.gov"})]}),t.jsxs(e.tr,{children:[t.jsx(e.td,{children:"data_source"}),t.jsx(e.td,{children:"str"}),t.jsx(e.td,{children:"The source of the clinical trial data"})]}),t.jsxs(e.tr,{children:[t.jsx(e.td,{children:"metadata"}),t.jsx(e.td,{children:"Dict[str, Any]"}),t.jsx(e.td,{children:"Additional metadata about the clinical trial"})]}),t.jsxs(e.tr,{children:[t.jsx(e.td,{children:"breadcrumbs"}),t.jsx(e.td,{children:"List[Breadcrumb]"}),t.jsx(e.td,{children:"List of breadcrumbs for this clinical trial entity"})]})]})]})]}),`
`]})}function h(i={}){const{wrapper:e}={...c(),...i.components};return e?t.jsx(e,{...i,children:t.jsx(l,{...i})}):l(i)}function a(i,e){throw new Error("Expected component `"+i+"` to be defined: you likely forgot to import, pass, or provide it.")}export{h as default};
