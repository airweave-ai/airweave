import { af as API_BASE_URL, ag as getAuthHeaders, ah as parseErrorResponse } from "./router-BGxBdlkD.mjs";
import { f as formatDate$1, D as DocsContent } from "./use-docs-content-CQG4H0bA.mjs";
import { jsxs, jsx } from "react/jsx-runtime";
async function fetchSources(token, orgId) {
  const response = await fetch(`${API_BASE_URL}/sources/`, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch sources"
    );
    throw new Error(message);
  }
  return response.json();
}
async function fetchSource(token, orgId, shortName) {
  const response = await fetch(`${API_BASE_URL}/sources/${shortName}`, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch source"
    );
    throw new Error(message);
  }
  return response.json();
}
function getAppIconUrl(shortName, theme) {
  const darkModeVariants = {
    attio: "attio-light.svg",
    notion: "notion-light.svg",
    clickup: "clickup-light.svg",
    github: "github-light.svg",
    linear: "linear-light.svg",
    zendesk: "zendesk-light.svg"
  };
  if (theme === "dark" && darkModeVariants[shortName]) {
    return `/icons/connectors/${darkModeVariants[shortName]}`;
  }
  return `/icons/connectors/${shortName}.svg`;
}
const formatDate = (dateString) => formatDate$1(dateString, "datetime");
function getCollectionStatusDisplay(status) {
  switch (status) {
    case "ACTIVE":
      return { label: "Active", variant: "success" };
    case "NEEDS_SOURCE":
      return { label: "Needs Source", variant: "warning" };
    case "ERROR":
      return { label: "Error", variant: "destructive" };
    default:
      return { label: status, variant: "default" };
  }
}
function CollectionsDocs() {
  return /* @__PURE__ */ jsx(DocsContent, { docPath: "concepts.mdx" });
}
function CollectionsCode() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Collections API" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Create and manage collections programmatically:" }),
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-auto rounded-lg p-3 text-xs", children: /* @__PURE__ */ jsx("code", { children: `import { Airweave } from '@airweave/sdk';

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
);` }) })
  ] });
}
function CollectionsHelp() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "About Collections" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Collections are searchable knowledge bases made up of synced data from one or more source connections." }),
    /* @__PURE__ */ jsx("div", { className: "space-y-3", children: /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
      /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Key Features" }),
      /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground mt-1 space-y-1 text-xs", children: [
        /* @__PURE__ */ jsx("li", { children: "Unified search across multiple sources" }),
        /* @__PURE__ */ jsx("li", { children: "Vector embeddings for semantic search" }),
        /* @__PURE__ */ jsx("li", { children: "Real-time data synchronization" })
      ] })
    ] }) })
  ] });
}
function CollectionDetailDocs() {
  return /* @__PURE__ */ jsx(DocsContent, { docPath: "search.mdx" });
}
function CollectionDetailCode({
  collectionId
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Search API" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Search this collection using the API:" }),
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-auto rounded-lg p-3 text-xs", children: /* @__PURE__ */ jsx("code", { children: `import { Airweave } from '@airweave/sdk';

const client = new Airweave({
  apiKey: process.env.AIRWEAVE_API_KEY
});

// Search the collection
const results = await client.collections.search(
  '${collectionId}',
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
}` }) })
  ] });
}
function CollectionDetailHelp() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Search Configuration" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Configure how your collection searches work." }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
      /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
        /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Search Methods" }),
        /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground mt-1 space-y-1 text-xs", children: [
          /* @__PURE__ */ jsxs("li", { children: [
            /* @__PURE__ */ jsx("strong", { children: "Hybrid" }),
            " - Combines semantic and keyword search"
          ] }),
          /* @__PURE__ */ jsxs("li", { children: [
            /* @__PURE__ */ jsx("strong", { children: "Neural" }),
            " - Pure semantic (embedding) search"
          ] }),
          /* @__PURE__ */ jsxs("li", { children: [
            /* @__PURE__ */ jsx("strong", { children: "Keyword" }),
            " - BM25 text matching"
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
        /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Toggle Features" }),
        /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground mt-1 space-y-1 text-xs", children: [
          /* @__PURE__ */ jsxs("li", { children: [
            /* @__PURE__ */ jsx("strong", { children: "Query Expansion" }),
            " - Generate query variations"
          ] }),
          /* @__PURE__ */ jsxs("li", { children: [
            /* @__PURE__ */ jsx("strong", { children: "Reranking" }),
            " - AI reorders results for relevance"
          ] }),
          /* @__PURE__ */ jsxs("li", { children: [
            /* @__PURE__ */ jsx("strong", { children: "Answer" }),
            " - Generate an AI-written answer"
          ] })
        ] })
      ] })
    ] })
  ] });
}
export {
  CollectionsHelp as C,
  formatDate as a,
  getAppIconUrl as b,
  CollectionsCode as c,
  CollectionsDocs as d,
  fetchSource as e,
  fetchSources as f,
  getCollectionStatusDisplay as g,
  CollectionDetailHelp as h,
  CollectionDetailCode as i,
  CollectionDetailDocs as j
};
