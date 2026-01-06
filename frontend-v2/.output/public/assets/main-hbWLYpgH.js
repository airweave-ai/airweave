import{j as e}from"./main-BEToz-TC.js";import{u as d}from"./use-docs-content-ogu5VP42.js";function o(t){const n={a:"a",h2:"h2",h3:"h3",li:"li",p:"p",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...d(),...t.components},{Accordion:r,Card:i}=n;return r||s("Accordion"),i||s("Card"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"24px"},children:[e.jsx("img",{src:"icon.svg",alt:"Word logo",width:"48",height:"48",className:"connector-icon"}),e.jsx("h1",{style:{margin:0},children:"Word"})]}),`
`,e.jsx(n.h2,{children:"Configuration"}),`
`,e.jsx(n.p,{children:"Microsoft Word source connector integrates with the Microsoft Graph API."}),`
`,e.jsx(n.p,{children:`Synchronizes Word documents from Microsoft OneDrive and SharePoint.
Documents are processed through Airweave's file handling pipeline which:`}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Downloads the .docx/.doc file"}),`
`,e.jsx(n.li,{children:"Converts to markdown for text extraction"}),`
`,e.jsx(n.li,{children:"Chunks content for vector search"}),`
`,e.jsx(n.li,{children:"Indexes for semantic search"}),`
`]}),`
`,e.jsx(n.p,{children:`It provides comprehensive access to Word documents with proper token refresh
and rate limiting.`}),`
`,e.jsx(i,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/word.py",children:e.jsx(n.p,{children:"Explore the Word connector implementation"})}),`
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
`,e.jsxs(r,{title:"WordDocumentEntity",children:[e.jsx(n.p,{children:"Schema for a Microsoft Word document as a file entity."}),e.jsx(n.p,{children:`Represents Word documents (.docx, .doc) stored in OneDrive/SharePoint.
Extends FileEntity to leverage Airweave's file processing pipeline which will:`}),e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:"Download the Word document"}),`
`,e.jsx(n.li,{children:"Convert it to markdown using document converters"}),`
`,e.jsx(n.li,{children:"Chunk the content for indexing"}),`
`]}),e.jsxs(n.p,{children:[`Reference:
`,e.jsx(n.a,{href:"https://learn.microsoft.com/en-us/graph/api/resources/driveitem",children:"https://learn.microsoft.com/en-us/graph/api/resources/driveitem"})]}),e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Field"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"title"}),e.jsx(n.td,{children:"str"}),e.jsx(n.td,{children:"The title/name of the document."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"web_url"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"URL to open the document in Word Online."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"content_download_url"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Direct download URL for the document content."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"created_by"}),e.jsx(n.td,{children:"Optional[Dict[str, Any]]"}),e.jsx(n.td,{children:"Identity of the user who created the document."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"last_modified_by"}),e.jsx(n.td,{children:"Optional[Dict[str, Any]]"}),e.jsx(n.td,{children:"Identity of the user who last modified the document."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"parent_reference"}),e.jsx(n.td,{children:"Optional[Dict[str, Any]]"}),e.jsx(n.td,{children:"Information about the parent folder/drive location."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"drive_id"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"ID of the drive containing this document."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"folder_path"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Full path to the parent folder."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"description"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Description of the document if available."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"shared"}),e.jsx(n.td,{children:"Optional[Dict[str, Any]]"}),e.jsx(n.td,{children:"Information about sharing status of the document."})]})]})]})]}),`
`]})}function l(t={}){const{wrapper:n}={...d(),...t.components};return n?e.jsx(n,{...t,children:e.jsx(o,{...t})}):o(t)}function s(t,n){throw new Error("Expected component `"+t+"` to be defined: you likely forgot to import, pass, or provide it.")}export{l as default};
