import{ap as a,aq as c,ar as o,j as e}from"./main-BEToz-TC.js";import{f as d,D as i}from"./use-docs-content-ogu5VP42.js";async function m(s,r){const t=await fetch(`${a}/sources/`,{headers:c(s,r)});if(!t.ok){const n=await o(t,"Failed to fetch sources");throw new Error(n)}return t.json()}async function x(s,r,t){const n=await fetch(`${a}/sources/${t}`,{headers:c(s,r)});if(!n.ok){const l=await o(n,"Failed to fetch source");throw new Error(l)}return n.json()}function g(s,r){const t={attio:"attio-light.svg",notion:"notion-light.svg",clickup:"clickup-light.svg",github:"github-light.svg",linear:"linear-light.svg",zendesk:"zendesk-light.svg"};return r==="dark"&&t[s]?`/icons/connectors/${t[s]}`:`/icons/connectors/${s}.svg`}const f=s=>d(s,"datetime");function j(s){switch(s){case"ACTIVE":return{label:"Active",variant:"success"};case"NEEDS_SOURCE":return{label:"Needs Source",variant:"warning"};case"ERROR":return{label:"Error",variant:"destructive"};default:return{label:s,variant:"default"}}}function p(){return e.jsx(i,{docPath:"concepts.mdx"})}function v(){return e.jsxs("div",{className:"space-y-4",children:[e.jsx("h3",{className:"text-base font-semibold",children:"Collections API"}),e.jsx("p",{className:"text-muted-foreground text-sm",children:"Create and manage collections programmatically:"}),e.jsx("pre",{className:"bg-muted overflow-auto rounded-lg p-3 text-xs",children:e.jsx("code",{children:`import { Airweave } from '@airweave/sdk';

const client = new Airweave({
  apiKey: process.env.AIRWEAVE_API_KEY
});

// Create a collection
const collection = await client.collections.create({
  name: 'My Collection'
});

// Search the collection
const results = await client.collections.search(
  collection.readable_id,
  { query: 'your search query' }
);`})})]})}function y(){return e.jsxs("div",{className:"space-y-4",children:[e.jsx("h3",{className:"text-base font-semibold",children:"About Collections"}),e.jsx("p",{className:"text-muted-foreground text-sm",children:"Collections are searchable knowledge bases made up of synced data from one or more source connections."}),e.jsx("div",{className:"space-y-3",children:e.jsxs("div",{className:"bg-muted rounded-lg p-3",children:[e.jsx("h4",{className:"text-sm font-medium",children:"Key Features"}),e.jsxs("ul",{className:"text-muted-foreground mt-1 space-y-1 text-xs",children:[e.jsx("li",{children:"Unified search across multiple sources"}),e.jsx("li",{children:"Vector embeddings for semantic search"}),e.jsx("li",{children:"Real-time data synchronization"})]})]})})]})}function w(){return e.jsx(i,{docPath:"search.mdx"})}function b({collectionId:s}){return e.jsxs("div",{className:"space-y-4",children:[e.jsx("h3",{className:"text-base font-semibold",children:"Search API"}),e.jsx("p",{className:"text-muted-foreground text-sm",children:"Search this collection using the API:"}),e.jsx("pre",{className:"bg-muted overflow-auto rounded-lg p-3 text-xs",children:e.jsx("code",{children:`import { Airweave } from '@airweave/sdk';

const client = new Airweave({
  apiKey: process.env.AIRWEAVE_API_KEY
});

// Search the collection
const results = await client.collections.search(
  '${s}',
  {
    query: 'your search query',
    retrieval_strategy: 'hybrid',
    rerank: true,
    generate_answer: true
  }
);

// Access results
for (const result of results.results) {
  console.log(result.name, result.score);
}`})})]})}function N(){return e.jsxs("div",{className:"space-y-4",children:[e.jsx("h3",{className:"text-base font-semibold",children:"Search Configuration"}),e.jsx("p",{className:"text-muted-foreground text-sm",children:"Configure how your collection searches work."}),e.jsxs("div",{className:"space-y-3",children:[e.jsxs("div",{className:"bg-muted rounded-lg p-3",children:[e.jsx("h4",{className:"text-sm font-medium",children:"Search Methods"}),e.jsxs("ul",{className:"text-muted-foreground mt-1 space-y-1 text-xs",children:[e.jsxs("li",{children:[e.jsx("strong",{children:"Hybrid"})," - Combines semantic and keyword search"]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Neural"})," - Pure semantic (embedding) search"]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Keyword"})," - BM25 text matching"]})]})]}),e.jsxs("div",{className:"bg-muted rounded-lg p-3",children:[e.jsx("h4",{className:"text-sm font-medium",children:"Toggle Features"}),e.jsxs("ul",{className:"text-muted-foreground mt-1 space-y-1 text-xs",children:[e.jsxs("li",{children:[e.jsx("strong",{children:"Query Expansion"})," - Generate query variations"]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Reranking"})," - AI reorders results for relevance"]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Answer"})," - Generate an AI-written answer"]})]})]})]})]})}export{y as C,g as a,v as b,p as c,m as d,x as e,f,j as g,N as h,b as i,w as j};
