import{j as e}from"./main-BEToz-TC.js";import{u as d}from"./use-docs-content-ogu5VP42.js";function l(r){const n={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",...d(),...r.components},{Accordion:i,Card:t,ParamField:o}=n;return i||s("Accordion"),t||s("Card"),o||s("ParamField"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"24px"},children:[e.jsx("img",{src:"icon.svg",alt:"Google Drive logo",width:"48",height:"48",className:"connector-icon"}),e.jsx("h1",{style:{margin:0},children:"Google Drive"})]}),`
`,e.jsx(n.h2,{children:"Configuration"}),`
`,e.jsx(n.p,{children:"Google Drive source connector integrates with the Google Drive API to extract files."}),`
`,e.jsx(n.p,{children:"Supports both personal Google Drive (My Drive) and shared drives."}),`
`,e.jsx(n.p,{children:`It supports downloading and processing files
while maintaining proper organization and access permissions.`}),`
`,e.jsx(t,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/google_drive.py",children:e.jsx(n.p,{children:"Explore the Google Drive connector implementation"})}),`
`,e.jsx(n.h3,{children:"Authentication"}),`
`,e.jsxs(n.p,{children:["This connector uses ",e.jsx(n.strong,{children:"OAuth 2.0 with custom credentials"}),". You need to provide your OAuth application's Client ID and Client Secret, then complete the OAuth consent flow."]}),`
`,e.jsx(t,{title:"OAuth Setup Required",className:"auth-setup-card",style:{backgroundColor:"rgba(59, 130, 246, 0.1)",padding:"16px",marginBottom:"24px"},children:e.jsxs(n.ol,{children:[`
`,e.jsx(n.li,{children:"Create an OAuth application in your provider's developer console"}),`
`,e.jsx(n.li,{children:"Enter your Client ID and Client Secret when configuring the connection"}),`
`,e.jsx(n.li,{children:"Complete the OAuth consent flow"}),`
`]})}),`
`,e.jsx(n.h3,{children:"Configuration Options"}),`
`,e.jsx(n.p,{children:"The following configuration options are available for this connector:"}),`
`,e.jsxs(t,{title:"Configuration Parameters",className:"config-card",style:{backgroundColor:"rgba(0, 0, 0, 0.05)",padding:"16px",marginBottom:"24px"},children:[e.jsx(n.p,{children:"Google Drive configuration schema."}),e.jsx(o,{path:"include_patterns",type:"list[str]",required:!1,default:"[]",children:e.jsx(n.p,{children:"List of file/folder paths to include in synchronization. Examples: 'my_folder/*', 'my_folder/my_file.pdf'. Separate multiple patterns with commas. If empty, all files are included."})})]}),`
`,e.jsx(n.h2,{children:"Data Models"}),`
`,e.jsx(n.p,{children:"The following data models are available for this connector:"}),`
`,e.jsxs(i,{title:"GoogleDriveDriveEntity",children:[e.jsx(n.p,{children:"Schema for a Drive resource (shared drive)."}),e.jsxs(n.p,{children:[`Reference:
`,e.jsx(n.a,{href:"https://developers.google.com/drive/api/v3/reference/drives",children:"https://developers.google.com/drive/api/v3/reference/drives"})]}),e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Field"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"kind"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:'Identifies what kind of resource this is; typically "drive#drive".'})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"color_rgb"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"The color of this shared drive as an RGB hex string."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"hidden"}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Whether the shared drive is hidden from default view."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"org_unit_id"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"The organizational unit of this shared drive, if applicable."})]})]})]})]}),`
`,e.jsxs(i,{title:"GoogleDriveFileEntity",children:[e.jsx(n.p,{children:"Schema for a File resource (in a user's or shared drive)."}),e.jsxs(n.p,{children:[`Reference:
`,e.jsx(n.a,{href:"https://developers.google.com/drive/api/v3/reference/files",children:"https://developers.google.com/drive/api/v3/reference/files"})]}),e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Field"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"description"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Optional description of the file."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"starred"}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Indicates whether the user has starred the file."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"trashed"}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Whether the file is in the trash."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"explicitly_trashed"}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Whether the file was explicitly trashed by the user."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"parents"}),e.jsx(n.td,{children:"List[str]"}),e.jsx(n.td,{children:"IDs of the parent folders containing this file."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"owners"}),e.jsx(n.td,{children:"List[Any]"}),e.jsx(n.td,{children:"Owners of the file."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"shared"}),e.jsx(n.td,{children:"bool"}),e.jsx(n.td,{children:"Whether the file is shared."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"web_view_link"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"Link for opening the file in a relevant Google editor or viewer."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"icon_link"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"A static, far-reaching URL to the file's icon."})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:"md5_checksum"}),e.jsx(n.td,{children:"Optional[str]"}),e.jsx(n.td,{children:"MD5 checksum for the content of the file."})]})]})]})]}),`
`,e.jsxs(i,{title:"GoogleDriveFileDeletionEntity",children:[e.jsx(n.p,{children:"Deletion signal for a Google Drive file."}),e.jsxs(n.p,{children:[`Emitted when the Drive Changes API reports a file was removed (deleted or access lost).
The `,e.jsx(n.code,{children:"entity_id"}),` matches the original file's ID so downstream deletion can target
the correct parent/children.`]}),e.jsx(n.table,{children:e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Field"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Description"})]})})})]}),`
`,`
`,e.jsx(n.h2,{children:"Integrate Airweave with Google APIs on localhost"}),`
`,e.jsxs(n.p,{children:[`This guide will walk you through connecting Google Workspace APIs to Airweave when running locally.
Google provides extensive `,e.jsx(n.a,{href:"https://developers.google.com/workspace/guides/get-started",children:"documentation"}),` on setting up your workspace.
Below is a streamlined process for connecting Google APIs to Airweave.`]}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.a,{href:"https://developers.google.com/workspace/guides/create-project",children:"Create a Google Cloud project"})," for your Google Workspace (if you don't already have one)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.a,{href:"https://developers.google.com/workspace/guides/enable-apis",children:"Enable the Google Workspace APIs"})," for Gmail, Google Calendar, and Google Drive"]}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://developers.google.com/workspace/guides/configure-oauth-consent",children:"Configure Google OAuth 2.0 consent screen"})}),`
`,e.jsxs(n.li,{children:["Under ",e.jsx(n.code,{children:"Audience"}),", select ",e.jsx(n.code,{children:"Make external"})," and add test users"]}),`
`,e.jsxs(n.li,{children:["Under ",e.jsx(n.code,{children:"Data Access"}),", add the following scopes:"]}),`
`]}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`https://www.googleapis.com/auth/docs
https://www.googleapis.com/auth/drive.photos.readonly
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/drive.metadata
https://www.googleapis.com/auth/drive.metadata.readonly
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/calendar.events.public.readonly
https://www.googleapis.com/auth/calendar.freebusy
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/calendar.calendars.readonly
https://www.googleapis.com/auth/calendar.events.owned.readonly
https://www.googleapis.com/auth/calendar.events.readonly
`})}),`
`,e.jsxs(n.ol,{start:"6",children:[`
`,e.jsxs(n.li,{children:[`
`,e.jsx(n.p,{children:e.jsx(n.a,{href:"https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",children:"Create OAuth client ID credentials"})}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:[`Under "Authorized redirect URIs," click "+ Add URI" and add the Redirect URI. Use the appropriate URL for your environment:
`,e.jsx(n.strong,{children:"Production (Airweave Cloud):"})]}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`https://api.airweave.ai/source-connections/callback
`})}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Local:"})}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{children:`http://localhost:8001/source-connections/callback
`})}),`
`]}),`
`,e.jsxs(n.li,{children:[`
`,e.jsxs(n.p,{children:["Locate the client ID and client secret from your newly created OAuth client. Add these credentials to the ",e.jsx(n.code,{children:"dev.integrations.yml"})," file to enable Google API integration."]}),`
`]}),`
`]})]})}function a(r={}){const{wrapper:n}={...d(),...r.components};return n?e.jsx(n,{...r,children:e.jsx(l,{...r})}):l(r)}function s(r,n){throw new Error("Expected component `"+r+"` to be defined: you likely forgot to import, pass, or provide it.")}export{a as default};
