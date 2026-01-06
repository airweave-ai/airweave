import{j as e}from"./main-BEToz-TC.js";import{u as s}from"./use-docs-content-ogu5VP42.js";function t(r){const n={a:"a",code:"code",h3:"h3",li:"li",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...s(),...r.components};return e.jsxs(e.Fragment,{children:[e.jsxs(n.p,{children:["The ",e.jsx(n.code,{children:"@airweave/vercel-ai-sdk"})," package provides an ",e.jsx(n.code,{children:"airweaveSearch"})," tool that integrates seamlessly with the ",e.jsx(n.a,{href:"https://ai-sdk.dev",children:"Vercel AI SDK"}),"."]}),`
`,e.jsx(n.h3,{children:"Prerequisites"}),`
`,e.jsx(n.p,{children:"Before you start you'll need:"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"A collection with data"}),": at least one source connection must have completed its initial sync. See the ",e.jsx(n.a,{href:"https://docs.airweave.ai/quickstart",children:"Quickstart"})," if you need to set this up."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"An API key"}),": Create one in the Airweave dashboard under ",e.jsx(n.strong,{children:"API Keys"}),"."]}),`
`]}),`
`,e.jsx(n.h3,{children:"Installation"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`npm install ai @ai-sdk/openai @airweave/vercel-ai-sdk
`})}),`
`,e.jsx(n.h3,{children:"Quick Start"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-typescript",children:`import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';
import { airweaveSearch } from '@airweave/vercel-ai-sdk';

const { text } = await generateText({
  model: openai('gpt-4o'),
  prompt: 'What were the key decisions from last week?',
  tools: {
    search: airweaveSearch({
      defaultCollection: 'my-knowledge-base',
    }),
  },
  maxSteps: 3,
});

console.log(text);
`})}),`
`,e.jsx(n.h3,{children:"Configuration"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-typescript",children:`airweaveSearch({
  // API key (defaults to AIRWEAVE_API_KEY env var)
  apiKey: 'your-api-key',

  // Default collection to search
  defaultCollection: 'my-collection',

  // Max results per search (default: 10)
  defaultLimit: 20,

  // Generate AI answer from results (default: false)
  generateAnswer: true,

  // Query expansion for better recall (default: true)
  expandQuery: true,

  // Rerank for relevance (default: true)
  rerank: true,

  // Base URL for self-hosted instances
  baseUrl: 'https://your-instance.airweave.ai',
});
`})}),`
`,e.jsx(n.h3,{children:"Configuration Options"}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Option"}),e.jsx(n.th,{children:"Type"}),e.jsx(n.th,{children:"Default"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"apiKey"})}),e.jsx(n.td,{children:"string"}),e.jsxs(n.td,{children:[e.jsx(n.code,{children:"AIRWEAVE_API_KEY"})," env"]}),e.jsx(n.td,{children:"Your Airweave API key"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"baseUrl"})}),e.jsx(n.td,{children:"string"}),e.jsx(n.td,{children:"-"}),e.jsx(n.td,{children:"Base URL for self-hosted instances"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"defaultCollection"})}),e.jsx(n.td,{children:"string"}),e.jsx(n.td,{children:"-"}),e.jsx(n.td,{children:"Default collection readable ID to search"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"defaultLimit"})}),e.jsx(n.td,{children:"number"}),e.jsx(n.td,{children:"10"}),e.jsx(n.td,{children:"Default maximum number of results"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"generateAnswer"})}),e.jsx(n.td,{children:"boolean"}),e.jsx(n.td,{children:"false"}),e.jsx(n.td,{children:"Generate an AI-powered answer from results"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"expandQuery"})}),e.jsx(n.td,{children:"boolean"}),e.jsx(n.td,{children:"true"}),e.jsx(n.td,{children:"Expand query with variations for better recall"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"rerank"})}),e.jsx(n.td,{children:"boolean"}),e.jsx(n.td,{children:"true"}),e.jsx(n.td,{children:"Rerank results for improved relevance"})]})]})]}),`
`,e.jsx(n.h3,{children:"Environment Variables"}),`
`,e.jsx(n.p,{children:"Set your API key as an environment variable. You can copy your API key from the Airweave dashboard."}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`AIRWEAVE_API_KEY=your-api-key
`})}),`
`,e.jsx(n.h3,{children:"TypeScript Support"}),`
`,e.jsx(n.p,{children:"Full TypeScript types are included:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-typescript",children:`import {
  airweaveSearch,
  AirweaveSearchOptions,
  AirweaveSearchResult,
  AirweaveSearchResultItem
} from '@airweave/vercel-ai-sdk';

const config: AirweaveSearchOptions = {
  defaultCollection: 'my-collection',
  defaultLimit: 10,
};

const search = airweaveSearch(config);
`})}),`
`,e.jsx(n.h3,{children:"Result Types"}),`
`,e.jsx(n.p,{children:"Each search result includes:"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-typescript",children:`interface AirweaveSearchResultItem {
  id: string;                    // Entity ID
  score: number;                 // Relevance score
  payload: {
    entity_id?: string;
    name?: string;
    created_at?: string;
    textual_representation?: string;
    breadcrumbs?: AirweaveBreadcrumb[];
    airweave_system_metadata?: {
      source_name?: string;      // e.g., "notion", "slack"
      entity_type?: string;      // e.g., "NotionPageEntity"
      sync_id?: string;
      chunk_index?: number;
    };
    // Plus source-specific fields
  };
}
`})}),`
`,e.jsx(n.h3,{children:"Learn More"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://ai-sdk.dev/docs/introduction",children:"Vercel AI SDK Documentation"})}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://ai-sdk.dev/tools-registry/airweave",children:"Airweave on Vercel Tool Registry"})}),`
`,e.jsx(n.li,{children:e.jsx(n.a,{href:"https://github.com/airweave-ai/airweave",children:"Airweave GitHub"})}),`
`]})]})}function l(r={}){const{wrapper:n}={...s(),...r.components};return n?e.jsx(n,{...r,children:e.jsx(t,{...r})}):t(r)}export{l as default};
