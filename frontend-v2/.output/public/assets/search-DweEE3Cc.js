import{j as e}from"./main-BEToz-TC.js";import{u as p}from"./use-docs-content-ogu5VP42.js";function u(s){const n={a:"a",code:"code",del:"del",em:"em",h2:"h2",h3:"h3",li:"li",ol:"ol",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...p(),...s.components},{Accordion:l,Card:a,CardGroup:o,CodeBlocks:r,CodeGroup:t,Note:d,Tip:h,Warning:c}=n;return l||i("Accordion"),a||i("Card"),o||i("CardGroup"),r||i("CodeBlocks"),t||i("CodeGroup"),d||i("Note"),h||i("Tip"),c||i("Warning"),e.jsxs(e.Fragment,{children:[e.jsxs(c,{children:[e.jsx(n.p,{children:e.jsx(n.strong,{children:"Search API Updated (October 2025)"})}),e.jsx(n.p,{children:"The search API has been updated. The legacy API continues to work, but we recommend migrating to the new API."}),e.jsxs(l,{title:"View Migration Details",children:[e.jsx(n.h3,{children:"What Changed?"}),e.jsx(n.p,{children:e.jsx(n.strong,{children:"Endpoints:"})}),e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.del,{children:e.jsx(n.code,{children:"GET /collections/{id}/search"})})," → Still works but deprecated"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"POST /collections/{id}/search"})," → Accepts both old and new schemas"]}),`
`]}),e.jsx(n.p,{children:e.jsx(n.strong,{children:"Request Schema:"})}),e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Legacy Field"}),e.jsx(n.th,{children:"New Field"}),e.jsx(n.th,{children:"Change"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsxs(n.td,{children:[e.jsx(n.code,{children:"response_type"})," (",e.jsx(n.code,{children:'"raw"'})," | ",e.jsx(n.code,{children:'"completion"'}),")"]}),e.jsxs(n.td,{children:[e.jsx(n.code,{children:"generate_answer"})," (boolean)"]}),e.jsx(n.td,{children:"Enum → Boolean"})]}),e.jsxs(n.tr,{children:[e.jsxs(n.td,{children:[e.jsx(n.code,{children:"expansion_strategy"})," (",e.jsx(n.code,{children:'"auto"'})," | ",e.jsx(n.code,{children:'"llm"'})," | ",e.jsx(n.code,{children:'"no_expansion"'}),")"]}),e.jsxs(n.td,{children:[e.jsx(n.code,{children:"expand_query"})," (boolean)"]}),e.jsx(n.td,{children:"Enum → Boolean"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"enable_query_interpretation"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"interpret_filters"})}),e.jsx(n.td,{children:"Renamed"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"search_method"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"retrieval_strategy"})}),e.jsx(n.td,{children:"Renamed"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"recency_bias"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"temporal_relevance"})}),e.jsx(n.td,{children:"Renamed"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"enable_reranking"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"rerank"})}),e.jsx(n.td,{children:"Renamed"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"score_threshold"})}),e.jsx(n.td,{children:e.jsx(n.em,{children:"(removed)"})}),e.jsx(n.td,{children:"Deprecated"})]})]})]}),e.jsx(n.h3,{children:"Full Comparison"}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

# Old GET endpoint with query params
response = await client.collections.search_collection(
    readable_id="my-collection",
    query="customer issues",
    response_type="completion",  # ❌
    limit=50,
    recency_bias=0.5,
)

# Old POST with verbose schema
from airweave.schemas.search import SearchRequest

request = SearchRequest(
    query="deployment procedures",
    response_type="completion",           # ❌
    expansion_strategy="auto",            # ❌
    enable_reranking=True,                # ✅
    enable_query_interpretation=True,     # ❌
    search_method="hybrid",               # ❌
    recency_bias=0.3,                     # ❌
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

# New POST-only endpoint with clean schema
from airweave.schemas.search import SearchRequest

request = SearchRequest(
    query="customer issues",
    generate_answer=True,         # ✅
    limit=50,
    temporal_relevance=0.5,       # ✅
)

response = await client.collections.search_collection(
    readable_id="my-collection",
    search_request=request
)

# Comprehensive example
request = SearchRequest(
    query="deployment procedures",
    generate_answer=True,         # ✅
    expand_query=True,            # ✅
    rerank=True,                  # ✅
    interpret_filters=True,       # ✅
    retrieval_strategy="hybrid",  # ✅
    temporal_relevance=0.3,       # ✅
)
`})})]}),e.jsx(n.h2,{children:"Migration Steps"}),e.jsx(n.h3,{children:"Step 1: Update Request Schema"}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`request = SearchRequest(
    query="test",
    response_type="completion",
    expansion_strategy="auto",
    enable_reranking=True,
    search_method="hybrid",
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`request = SearchRequest(
    query="test",
    generate_answer=True,
    expand_query=True,
    rerank=True,
    retrieval_strategy="hybrid",
)
`})})]}),e.jsx(n.h3,{children:"Step 2: Update Response Handling"}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`response = await client.collections.search_collection(...)

# Old response structure
if response.status == "success":
    if response.response_type == "completion":
        print(response.completion)
    else:
        print(response.results)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`response = await client.collections.search_collection(...)

# New response structure
if response.completion:
    print(response.completion)
else:
    print(response.results)
`})})]}),e.jsx(n.h3,{children:"Step 3: Remove Deprecated Fields"}),e.jsx(n.p,{children:"The new response no longer includes:"}),e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"status"})," field"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"response_type"})," field"]}),`
`]}),e.jsx(n.h2,{children:"REST API Migration"}),e.jsx(n.h3,{children:"GET Endpoint (Deprecated)"}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X GET "https://api.airweave.ai/collections/{id}/search?query=test&response_type=completion" \\
  -H "x-api-key: your-api-key"
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST "https://api.airweave.ai/collections/{id}/search" \\
  -H "x-api-key: your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "test",
    "generate_answer": true
  }'
`})})]}),e.jsx(n.h3,{children:"POST Endpoint Schema"}),e.jsxs(t,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`{
  "query": "test",
  "response_type": "completion",
  "expansion_strategy": "auto",
  "enable_reranking": true,
  "search_method": "hybrid"
}
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`{
  "query": "test",
  "generate_answer": true,
  "expand_query": true,
  "rerank": true,
  "retrieval_strategy": "hybrid"
}
`})})]}),e.jsx(n.h3,{children:"Detecting Deprecation"}),e.jsx(n.p,{children:"When using the legacy API, you'll receive HTTP headers indicating deprecation:"}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-http",children:`X-API-Deprecation: true
X-API-Deprecation-Message: ...
`})})]})]}),`
`,e.jsx(n.p,{children:"Airweave lets you search across all your connected data sources through one unified interface. When you query a collection, Airweave runs a multi-step search pipeline that combines AI understanding with keyword precision. You can start with the defaults or configure each step for full control."}),`
`,e.jsx(d,{children:e.jsxs(n.p,{children:["Want to try out our search right now? Head to our ",e.jsx(n.a,{href:"https://docs.airweave.ai/api-reference/collections/search-collections-readable-id-search-post",children:"interactive API documentation"})," where you can test search queries directly in your browser!"]})}),`
`,e.jsx(n.h2,{children:"Quick Reference"}),`
`,e.jsx(n.p,{children:"Here are the default settings Airweave uses. You can override any of these in your queries."}),`
`,e.jsxs(n.table,{children:[e.jsx(n.thead,{children:e.jsxs(n.tr,{children:[e.jsx(n.th,{children:"Parameter"}),e.jsx(n.th,{children:"Default"}),e.jsx(n.th,{children:"Description"})]})}),e.jsxs(n.tbody,{children:[e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"expand_query"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"true"})}),e.jsx(n.td,{children:"Generate query variations for better recall"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"retrieval_strategy"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"hybrid"})}),e.jsx(n.td,{children:"Combines AI semantic search with keyword matching"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"interpret_filters"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"false"})}),e.jsx(n.td,{children:"Extract filters from natural language (you control manually by default)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"rerank"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"true"})}),e.jsx(n.td,{children:"LLM-based result reordering (adds ~10s latency)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"temporal_relevance"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"0.3"})}),e.jsx(n.td,{children:"Weight toward recent content (0.0-1.0)"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"generate_answer"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"true"})}),e.jsx(n.td,{children:"Generate AI completion from results"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"limit"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"1000"})}),e.jsx(n.td,{children:"Maximum results to return"})]}),e.jsxs(n.tr,{children:[e.jsx(n.td,{children:e.jsx(n.code,{children:"offset"})}),e.jsx(n.td,{children:e.jsx(n.code,{children:"0"})}),e.jsx(n.td,{children:"Results to skip for pagination"})]})]})]}),`
`,e.jsx(n.h2,{children:"Which endpoint to use"}),`
`,e.jsxs(o,{cols:2,children:[e.jsxs(a,{title:"Simple Search (Deprecated)",icon:"magnifying-glass",href:"/api-reference/collections/search-collections-readable-id-search-get",children:[e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"GET"})," ",e.jsx(n.code,{children:"/collections/{readable_id}/search"})]}),e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"⚠️ Deprecated:"})," This endpoint is maintained for backwards compatibility only. Use POST for new integrations."]})]}),e.jsxs(a,{title:"Advanced Search (Recommended)",icon:"sliders",href:"/api-reference/collections/search-collections-readable-id-search-post",children:[e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"POST"})," ",e.jsx(n.code,{children:"/collections/{readable_id}/search"})]}),e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Recommended:"})," Full control. Use this for all new integrations."]})]})]}),`
`,e.jsx(n.h2,{children:"How Airweave search works"}),`
`,e.jsx(n.p,{children:"Each search runs through a multi step pipeline. Understanding the stages helps explain why different parameters exist and when to use them:"}),`
`,e.jsxs(n.ol,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Query expansion"}),": Generate variations of the user query to capture synonyms and related terms."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Retrieval"}),": Use keyword, neural, or hybrid methods to fetch candidate documents."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Filtering"}),": Apply structured metadata filters before or during retrieval."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Recency bias"}),": Optionally weight results toward fresher content."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Reranking"}),": Use AI to reorder the top results for higher precision."]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"Answer generation"}),": Return raw documents or synthesize a natural language response."]}),`
`]}),`
`,e.jsx(n.p,{children:"Defaults are designed to work out of the box, and you can override any stage as needed."}),`
`,e.jsx(n.h2,{children:"Parameters"}),`
`,e.jsx(n.h3,{children:"Query Expansion"}),`
`,e.jsx(n.p,{children:"Expands your query to catch related terms and synonyms that may not appear verbatim in your documents. This improves recall when wording differs but meaning is the same."}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"expand_query"})," (boolean)"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"true"})," (default): Generate query variations for better recall"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"false"}),": Search only for your exact query"]}),`
`]}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "customer churn analysis",
    "expand_query": true
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

results = await client.collections.search_advanced(
    "your-collection-id",
    {
        "query": "customer churn analysis",
        "expand_query": true
    }
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });

const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "payment failures",
    expandQuery: true,
  }
);
`})})]}),`
`,e.jsx(n.h3,{children:"Search Method"}),`
`,e.jsx(n.p,{children:"The search method determines how Airweave searches your data. Different methods balance semantic understanding and keyword precision. You can use AI to understand meaning, traditional keyword matching, or both."}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"retrieval_strategy"})]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"hybrid"})," (default): Best of both worlds - finds results by meaning AND exact keywords"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"neural"}),": AI-powered search that understands what you mean, not just what you type"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"keyword"}),": Traditional search that looks for exact word matches"]}),`
`]}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "authentication flow security vulnerabilities",
    "retrieval_strategy": "hybrid"
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    "your-collection-id",
    {
        "query": "authentication flow security vulnerabilities",
        "retrieval_strategy": "hybrid"
    }
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "authentication flow security vulnerabilities",
    retrievalStrategy: "hybrid",
  }
);
`})})]}),`
`,e.jsx(n.h3,{children:"Filtering Results"}),`
`,e.jsx(n.p,{children:"Applies structured filters before search, ensuring only relevant subsets are scanned. Useful for large datasets or when results must match specific attributes like source, date, or status."}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"filter"})]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Example 1: Filter by source"})}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "deployment issues",
    "filter": {
      "must": [{
        "key": "source_name",
        "match": {"value": "GitHub"}
      }]
    }
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    "your-collection-id",
    {
        "query": "deployment issues",
        "filter": {
            "must": [{
                "key": "source_name",
                "match": {"value": "GitHub"}  # Case-sensitive!
            }]
        }
    }
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "deployment issues",
    filter: {
      must: [{
        key: "source_name",
        match: { value: "GitHub" }  // Case-sensitive!
      }]
    }
  }
);
`})})]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Example 2: Multiple filters"})}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "customer feedback",
    "filter": {
      "must": [
        {
          "key": "source_name",
          "match": {"any": ["Zendesk", "Intercom", "Slack"]}
        },
        {
          "key": "created_at",
          "range": {
            "gte": "2024-01-01T00:00:00Z"
          }
        }
      ]
    }
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from datetime import datetime, timezone, timedelta

results = await client.collections.search_advanced(
    "your-collection-id",
    {
        "query": "customer feedback",
        "filter": {
            "must": [
                {
                    "key": "source_name",
                    "match": {"any": ["Zendesk", "Intercom", "Slack"]}
                },
                {
                    "key": "created_at",
                    "range": {
                        "gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                    }
                }
            ]
        }
    }
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const oneWeekAgo = new Date();
oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "customer feedback",
    filter: {
      must: [
        {
          key: "source_name",
          match: { any: ["Zendesk", "Intercom", "Slack"] }
        },
        {
          key: "created_at",
          range: {
            gte: oneWeekAgo.toISOString()
          }
        }
      ]
    }
  }
);
`})})]}),`
`,e.jsx(n.p,{children:e.jsx(n.strong,{children:"Example 3: Exclude results"})}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "bug reports",
    "filter": {
      "must_not": [{
        "key": "status",
        "match": {"any": ["resolved", "closed", "done"]}
      }]
    }
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    "your-collection-id",
    {
        "query": "bug reports",
        "filter": {
            "must_not": [{
                "key": "status",
                "match": {"any": ["resolved", "closed", "done"]}
            }]
        }
    }
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "bug reports",
    filter: {
      must_not: [{
        key: "status",
        match: { any: ["resolved", "closed", "done"] }
      }]
    }
  }
);
`})})]}),`
`,e.jsx(n.h3,{children:"Query Interpretation"}),`
`,e.jsx(c,{children:e.jsx(n.p,{children:"This feature is currently in beta. It can occasionally filter too narrowly, so verify result counts."})}),`
`,e.jsx(n.p,{children:"Query interpretation allows Airweave to automatically extract structured filters from a natural language query. Instead of manually defining metadata filters, you can simply describe what you are looking for, and Airweave will translate that description into filter conditions."}),`
`,e.jsxs(n.p,{children:["This feature is useful when you want to let end users search in plain English, for example ",e.jsx(n.em,{children:'"open GitHub issues from last week"'})," or ",e.jsx(n.em,{children:'"critical bugs reported this month"'}),". Airweave analyzes the query, identifies entities like dates, sources, or statuses, and applies them as filters."]}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"interpret_filters"})," (boolean)"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"false"})," (default): You control all filters manually"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"true"}),": AI extracts filters from your natural language query"]}),`
`]}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "open asana tickets from last week",
    "interpret_filters": true
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="open asana tickets from last week",
    interpret_filters=True
)
# AI understands: Asana source, open status, last 7 days

results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="critical bugs from GitHub this month",
    interpret_filters=True
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "open asana tickets from last week",
    interpretFilters: true
  }
);

const response2 = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "critical bugs from GitHub this month",
    interpretFilters: true
  }
);
`})})]}),`
`,e.jsx(n.h3,{children:"Temporal Relevance"}),`
`,e.jsxs(h,{children:["Learn more about this topic in our blogpost: ",e.jsx(n.a,{href:"https://airweave.ai/blog/temporal-relevance-explained",children:"Deep Dive on Temporal Relevance "}),"."]}),`
`,e.jsx(n.p,{children:"Temporal relevance adjusts the results ranking to prefer newer documents. This is valuable for time-sensitive data like messages, customer feedback, tickets, or news."}),`
`,e.jsx(n.p,{children:"The scoring formula adjusts results based on age:"}),`
`,e.jsx(n.p,{children:e.jsxs(n.strong,{children:["S",e.jsx("sub",{children:"final"})," = S",e.jsx("sub",{children:"similarity"})," × (1 − β + β × d(t))"]})}),`
`,e.jsx(n.p,{children:"where,"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsxs(n.strong,{children:["S",e.jsx("sub",{children:"final"})]})," = final relevance score"]}),`
`,e.jsxs(n.li,{children:[e.jsxs(n.strong,{children:["S",e.jsx("sub",{children:"similarity"})]})," = semantic similarity score"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"β"})," = recency bias parameter (0 to 1)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:"d(t)"})," = time decay factor (0 = oldest, 1 = newest)."]}),`
`]}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"temporal_relevance"})," (0.0 to 1.0)"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"0.3"})," (default): Slightly prefer newer content"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"0.0"}),": Don't care about dates, just find the best matches"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"1.0"}),": Heavily prioritize the newest content"]}),`
`]}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "project updates",
    "temporal_relevance": 0.7
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="project updates",
    temporal_relevance=0.7
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "project updates",
    temporalRelevance: 0.7,
  }
);
`})})]}),`
`,e.jsx(n.p,{children:"Use this when freshness matters. For example, prioritizing the latest bug reports or recent customer complaints over historical ones."}),`
`,e.jsx(n.h3,{children:"Pagination"}),`
`,e.jsx(n.p,{children:"Control how many results you get and navigate through large result sets."}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameters"}),":"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"limit"}),": How many results to return (1-1000, default: 20)"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"offset"}),": How many results to skip (for pagination, default: 0)"]}),`
`]}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`# Simple search with pagination
curl -X GET 'https://api.airweave.ai/collections/your-collection-id/search?query=data%20retention%20policies&limit=50&offset=50' \\
  -H 'x-api-key: YOUR_API_KEY'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`response = await client.collections.search_collection(
    readable_id="your-collection-id",
    query="data retention policies",
    limit=50,
    offset=50,  # Skip first 50
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchCollection({
  readableId: "your-collection-id",
  query: "data retention policies",
  limit: 50,
  offset: 50,
});
`})})]}),`
`,e.jsx(n.h3,{children:"AI Reranking"}),`
`,e.jsx(n.p,{children:"AI reranking takes the top set of results from the initial search and reorders them using a large language model. This improves accuracy in cases where keyword or semantic similarity alone might be misleading."}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"rerank"})," (boolean)"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"true"})," (default): AI reviews and reorders results for best relevance"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"false"}),": Skip reranking for faster results"]}),`
`]}),`
`,e.jsx(c,{children:e.jsx(n.p,{children:"Reranking adds about 10 seconds to your search. Turn it off if you need fast results."})}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "user authentication methods",
    "rerank": false
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="user authentication methods",
    rerank=False
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "user authentication methods",
    rerank: false,
  }
);
`})})]}),`
`,e.jsx(n.h3,{children:"Generate AI Answers"}),`
`,e.jsx(n.p,{children:"Airweave can return either raw results or a synthesized answer. When enabled, a large language model generates a natural language response based on the top results, including sources when available."}),`
`,e.jsxs(n.p,{children:[e.jsx(n.strong,{children:"Parameter"}),": ",e.jsx(n.code,{children:"generate_answer"})," (boolean)"]}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"true"})," (default): Generate an AI-synthesized answer from the top search results"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.code,{children:"false"}),": Return only raw results"]}),`
`]}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "What are our customer refund policies?",
    "generate_answer": true
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="What are our customer refund policies?",
    generate_answer=True
)
# Access: results.completion
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "What are our customer refund policies?",
    generateAnswer: true,
  }
);
// Access: response.completion
`})})]}),`
`,e.jsx(n.h2,{children:"Complete example"}),`
`,e.jsx(n.p,{children:"Here's everything together in one search using the new API:"}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "customer feedback about pricing",
    "expand_query": true,
    "retrieval_strategy": "hybrid",
    "filter": {
      "must": [{
        "key": "source_name",
        "match": {"any": ["Zendesk", "Slack"]}
      }]
    },
    "temporal_relevance": 0.5,
    "rerank": true,
    "generate_answer": false,
    "limit": 50,
    "offset": 0
  }'
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK
from datetime import datetime, timezone, timedelta

client = AirweaveSDK(api_key="YOUR_API_KEY")

results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="customer feedback about pricing",
    expand_query=True,
    retrieval_strategy="hybrid",
    filter={
        "must": [{
            "key": "source_name",
            "match": {"any": ["Zendesk", "Slack"]}
        }]
    },
    temporal_relevance=0.5,
    rerank=True,
    generate_answer=False,
    limit=50,
    offset=0
)
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-javascript",children:`import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });

const response = await client.collections.searchAdvanced(
  "your-collection-id",
  {
    query: "customer feedback about pricing",
    expandQuery: true,
    retrievalStrategy: "hybrid",
    filter: {
      must: [{
        key: "source_name",
        match: { any: ["Zendesk", "Slack"] }
      }]
    },
    temporalRelevance: 0.5,
    rerank: true,
    generateAnswer: false,
    limit: 50,
    offset: 0
  }
);
`})})]}),`
`,e.jsx(n.h3,{children:"Legacy API Example"}),`
`,e.jsx(n.p,{children:"If you're still using the legacy API, here's how the same query looks (deprecated):"}),`
`,e.jsxs(r,{children:[e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "customer feedback about pricing",
    "expansion_strategy": "auto",
    "search_method": "hybrid",
    "filter": {
      "must": [{
        "key": "source_name",
        "match": {"any": ["Zendesk", "Slack"]}
      }]
    },
    "recency_bias": 0.5,
    "enable_reranking": true,
    "response_type": "raw",
    "limit": 50,
    "offset": 0
  }'
# Response will include X-API-Deprecation header
`})}),e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`# Using old parameter names (still works but deprecated)
results = await client.collections.search_advanced(
    readable_id="your-collection-id",
    query="customer feedback about pricing",
    expansion_strategy="auto",  # ❌ Use expand_query instead
    search_method="hybrid",     # ❌ Use retrieval_strategy instead
    recency_bias=0.5,           # ❌ Use temporal_relevance instead
    enable_reranking=True,      # ❌ Use rerank instead
    response_type="raw",        # ❌ Use generate_answer instead
)
`})})]}),`
`,e.jsx(a,{title:"Ready to search?",icon:"rocket",children:e.jsxs(n.p,{children:["Try these examples live in our ",e.jsx(n.a,{href:"https://docs.airweave.ai/api-reference/collections/search-collections-readable-id-search-post",children:"interactive API documentation"}),". You can execute real searches and see responses instantly!"]})})]})}function y(s={}){const{wrapper:n}={...p(),...s.components};return n?e.jsx(n,{...s,children:e.jsx(u,{...s})}):u(s)}function i(s,n){throw new Error("Expected component `"+s+"` to be defined: you likely forgot to import, pass, or provide it.")}export{y as default};
