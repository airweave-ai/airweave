import{j as e}from"./main-BEToz-TC.js";import{u as o}from"./use-docs-content-ogu5VP42.js";function d(s){const t={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",...o(),...s.components},{Accordion:r,Card:i,ParamField:n}=t;return r||l("Accordion"),i||l("Card"),n||l("ParamField"),e.jsxs(e.Fragment,{children:[`
`,e.jsxs("div",{className:"connector-header",style:{display:"flex",alignItems:"center",gap:"12px",marginBottom:"24px"},children:[e.jsx("img",{src:"icon.svg",alt:"Gmail logo",width:"48",height:"48",className:"connector-icon"}),e.jsx("h1",{style:{margin:0},children:"Gmail"})]}),`
`,e.jsx(t.h2,{children:"Configuration"}),`
`,e.jsx(t.p,{children:"Gmail source connector integrates with the Gmail API to extract and synchronize email data."}),`
`,e.jsx(t.p,{children:"Connects to your Gmail account."}),`
`,e.jsx(t.p,{children:"It supports syncing email threads, individual messages, and file attachments."}),`
`,e.jsx(i,{title:"View Source Code",icon:"brands github",href:"https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/gmail.py",children:e.jsx(t.p,{children:"Explore the Gmail connector implementation"})}),`
`,e.jsx(t.h3,{children:"Authentication"}),`
`,e.jsxs(t.p,{children:["This connector uses ",e.jsx(t.strong,{children:"OAuth 2.0 with custom credentials"}),". You need to provide your OAuth application's Client ID and Client Secret, then complete the OAuth consent flow."]}),`
`,e.jsx(i,{title:"OAuth Setup Required",className:"auth-setup-card",style:{backgroundColor:"rgba(59, 130, 246, 0.1)",padding:"16px",marginBottom:"24px"},children:e.jsxs(t.ol,{children:[`
`,e.jsx(t.li,{children:"Create an OAuth application in your provider's developer console"}),`
`,e.jsx(t.li,{children:"Enter your Client ID and Client Secret when configuring the connection"}),`
`,e.jsx(t.li,{children:"Complete the OAuth consent flow"}),`
`]})}),`
`,e.jsx(t.h3,{children:"Configuration Options"}),`
`,e.jsx(t.p,{children:"The following configuration options are available for this connector:"}),`
`,e.jsxs(i,{title:"Configuration Parameters",className:"config-card",style:{backgroundColor:"rgba(0, 0, 0, 0.05)",padding:"16px",marginBottom:"24px"},children:[e.jsx(t.p,{children:"Gmail configuration schema."}),e.jsx(n,{path:"after_date",type:"Optional[str]",required:!0,children:e.jsx(t.p,{children:"Sync emails after this date (format: YYYY/MM/DD or YYYY-MM-DD)."})}),e.jsx(n,{path:"included_labels",type:"list[str]",required:!1,default:"[]",children:e.jsx(t.p,{children:"Labels to include (e.g., 'inbox', 'sent', 'important'). Defaults to inbox and sent."})}),e.jsx(n,{path:"excluded_labels",type:"list[str]",required:!1,default:"[]",children:e.jsx(t.p,{children:"Labels to exclude (e.g., 'spam', 'trash', 'promotions', 'social'). Defaults to spam and trash."})}),e.jsx(n,{path:"excluded_categories",type:"list[str]",required:!1,default:"[]",children:e.jsx(t.p,{children:"Gmail categories to exclude (e.g., 'promotions', 'social', 'updates', 'forums')."})}),e.jsx(n,{path:"gmail_query",type:"Optional[str]",required:!0,children:e.jsx(t.p,{children:"Advanced. Custom Gmail query string (overrides all other filters if provided)."})})]}),`
`,e.jsx(t.h2,{children:"Data Models"}),`
`,e.jsx(t.p,{children:"The following data models are available for this connector:"}),`
`,e.jsxs(r,{title:"GmailThreadEntity",children:[e.jsx(t.p,{children:"Schema for Gmail thread entities."}),e.jsxs(t.p,{children:["Reference: ",e.jsx(t.a,{href:"https://developers.google.com/gmail/api/reference/rest/v1/users.threads",children:"https://developers.google.com/gmail/api/reference/rest/v1/users.threads"})]}),e.jsxs(t.table,{children:[e.jsx(t.thead,{children:e.jsxs(t.tr,{children:[e.jsx(t.th,{children:"Field"}),e.jsx(t.th,{children:"Type"}),e.jsx(t.th,{children:"Description"})]})}),e.jsxs(t.tbody,{children:[e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"snippet"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"A short snippet from the thread"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"history_id"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"The thread's history ID"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"message_count"}),e.jsx(t.td,{children:"Optional[int]"}),e.jsx(t.td,{children:"Number of messages in the thread"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"label_ids"}),e.jsx(t.td,{children:"List[str]"}),e.jsx(t.td,{children:"Labels applied to this thread"})]})]})]})]}),`
`,e.jsxs(r,{title:"GmailMessageEntity",children:[e.jsx(t.p,{children:"Schema for Gmail message entities."}),e.jsxs(t.p,{children:["Reference: ",e.jsx(t.a,{href:"https://developers.google.com/gmail/api/reference/rest/v1/users.messages",children:"https://developers.google.com/gmail/api/reference/rest/v1/users.messages"})]}),e.jsxs(t.table,{children:[e.jsx(t.thead,{children:e.jsxs(t.tr,{children:[e.jsx(t.th,{children:"Field"}),e.jsx(t.th,{children:"Type"}),e.jsx(t.th,{children:"Description"})]})}),e.jsxs(t.tbody,{children:[e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"thread_id"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"ID of the thread this message belongs to"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"subject"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Subject line of the message"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"sender"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Email address of the sender"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"to"}),e.jsx(t.td,{children:"List[str]"}),e.jsx(t.td,{children:"Recipients of the message"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"cc"}),e.jsx(t.td,{children:"List[str]"}),e.jsx(t.td,{children:"CC recipients"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"bcc"}),e.jsx(t.td,{children:"List[str]"}),e.jsx(t.td,{children:"BCC recipients"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"date"}),e.jsx(t.td,{children:"Optional[datetime]"}),e.jsx(t.td,{children:"Date the message was sent"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"snippet"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Brief snippet of the message content"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"label_ids"}),e.jsx(t.td,{children:"List[str]"}),e.jsx(t.td,{children:"Labels applied to this message"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"internal_date"}),e.jsx(t.td,{children:"Optional[datetime]"}),e.jsx(t.td,{children:"Internal Gmail timestamp"})]})]})]})]}),`
`,e.jsxs(r,{title:"GmailAttachmentEntity",children:[e.jsx(t.p,{children:"Schema for Gmail attachment entities."}),e.jsxs(t.p,{children:["Reference: ",e.jsx(t.a,{href:"https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments",children:"https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments"})]}),e.jsxs(t.table,{children:[e.jsx(t.thead,{children:e.jsxs(t.tr,{children:[e.jsx(t.th,{children:"Field"}),e.jsx(t.th,{children:"Type"}),e.jsx(t.th,{children:"Description"})]})}),e.jsxs(t.tbody,{children:[e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"message_id"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"ID of the message this attachment belongs to"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"attachment_id"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"Gmail's attachment ID"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"thread_id"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"ID of the thread containing the message"})]})]})]})]}),`
`,e.jsxs(r,{title:"GmailMessageDeletionEntity",children:[e.jsx(t.p,{children:"Deletion signal for a Gmail message."}),e.jsxs(t.p,{children:[`Emitted when the Gmail History API reports a messageDeleted. The entity_id matches the
message entity's ID format (msg_`,message_id,`) so downstream deletion removes the
correct parent/children.`]}),e.jsxs(t.table,{children:[e.jsx(t.thead,{children:e.jsxs(t.tr,{children:[e.jsx(t.th,{children:"Field"}),e.jsx(t.th,{children:"Type"}),e.jsx(t.th,{children:"Description"})]})}),e.jsxs(t.tbody,{children:[e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"message_id"}),e.jsx(t.td,{children:"str"}),e.jsx(t.td,{children:"The Gmail message ID that was deleted"})]}),e.jsxs(t.tr,{children:[e.jsx(t.td,{children:"thread_id"}),e.jsx(t.td,{children:"Optional[str]"}),e.jsx(t.td,{children:"Thread ID (optional if not provided by change record)"})]})]})]})]}),`
`,`
`,e.jsx(t.h2,{children:"Integrate Airweave with Google APIs on localhost"}),`
`,e.jsxs(t.p,{children:[`This guide will walk you through connecting Google Workspace APIs to Airweave when running locally.
Google provides extensive `,e.jsx(t.a,{href:"https://developers.google.com/workspace/guides/get-started",children:"documentation"}),` on setting up your workspace.
Below is a streamlined process for connecting Google APIs to Airweave.`]}),`
`,e.jsxs(t.ol,{children:[`
`,e.jsxs(t.li,{children:[e.jsx(t.a,{href:"https://developers.google.com/workspace/guides/create-project",children:"Create a Google Cloud project"})," for your Google Workspace (if you don't already have one)"]}),`
`,e.jsxs(t.li,{children:[e.jsx(t.a,{href:"https://developers.google.com/workspace/guides/enable-apis",children:"Enable the Google Workspace APIs"})," for Gmail, Google Calendar, and Google Drive"]}),`
`,e.jsx(t.li,{children:e.jsx(t.a,{href:"https://developers.google.com/workspace/guides/configure-oauth-consent",children:"Configure Google OAuth 2.0 consent screen"})}),`
`,e.jsxs(t.li,{children:["Under ",e.jsx(t.code,{children:"Audience"}),", select ",e.jsx(t.code,{children:"Make external"})," and add test users"]}),`
`,e.jsxs(t.li,{children:["Under ",e.jsx(t.code,{children:"Data Access"}),", add the following scopes:"]}),`
`]}),`
`,e.jsx(t.pre,{children:e.jsx(t.code,{children:`https://www.googleapis.com/auth/docs
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
`,e.jsxs(t.ol,{start:"6",children:[`
`,e.jsxs(t.li,{children:[`
`,e.jsx(t.p,{children:e.jsx(t.a,{href:"https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",children:"Create OAuth client ID credentials"})}),`
`]}),`
`,e.jsxs(t.li,{children:[`
`,e.jsx(t.p,{children:'Under "Authorized redirect URIs," click "+ Add URI" and add the Redirect URI. Use the appropriate URL for your environment:'}),`
`,e.jsx(t.p,{children:e.jsx(t.strong,{children:"Production (Airweave Cloud):"})}),`
`,e.jsx(t.pre,{children:e.jsx(t.code,{children:`https://api.airweave.ai/source-connections/callback
`})}),`
`,e.jsx(t.p,{children:e.jsx(t.strong,{children:"Local:"})}),`
`,e.jsx(t.pre,{children:e.jsx(t.code,{children:`http://localhost:8001/source-connections/callback
`})}),`
`]}),`
`,e.jsxs(t.li,{children:[`
`,e.jsxs(t.p,{children:["Locate the client ID and client secret from your newly created OAuth client. Add these credentials to the ",e.jsx(t.code,{children:"dev.integrations.yml"})," file to enable Google API integration."]}),`
`]}),`
`]})]})}function h(s={}){const{wrapper:t}={...o(),...s.components};return t?e.jsx(t,{...s,children:e.jsx(d,{...s})}):d(s)}function l(s,t){throw new Error("Expected component `"+s+"` to be defined: you likely forgot to import, pass, or provide it.")}export{h as default};
