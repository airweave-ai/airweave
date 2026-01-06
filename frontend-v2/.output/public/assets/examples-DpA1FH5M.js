import{j as e}from"./main-BEToz-TC.js";import{u as a}from"./use-docs-content-ogu5VP42.js";function r(i){const n={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",p:"p",pre:"pre",strong:"strong",ul:"ul",...a(),...i.components},{Tip:t}=n;return t||s("Tip"),e.jsxs(e.Fragment,{children:[e.jsx(n.p,{children:"This page provides quick examples to get you started with Airweave search. For a comprehensive, hands-on tutorial with visualizations and real-world scenarios, check out our interactive Jupyter notebook."}),`
`,e.jsxs(t,{title:"Interactive Tutorial",children:[e.jsx(n.p,{children:"Learn search concepts through hands-on examples in our comprehensive Jupyter notebook with live code, visualizations, and real-world scenarios."}),e.jsx(n.p,{children:e.jsx(n.a,{href:"https://github.com/airweave-ai/airweave/blob/main/examples/04_advanced_search_with_filters.ipynb",children:"View the Advanced Search Tutorial →"})})]}),`
`,e.jsx(n.h2,{children:"Quick Start"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from airweave import AirweaveSDK
from airweave.schemas.search import SearchRequest
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

client = AirweaveSDK(api_key="your-api-key")
`})}),`
`,e.jsx(n.h2,{children:"Essential Examples"}),`
`,e.jsx(n.h3,{children:"Basic Search"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`# Simple text search
response = await client.collections.search_collection(
    readable_id="your-collection-id",
    query="customer onboarding process"
)
`})}),`
`,e.jsx(n.h3,{children:"Search with AI Completion"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`# Get AI-generated insights
response = await client.collections.search_collection(
    readable_id="your-collection-id",
    query="What are our security policies?",
    response_type="completion"
)
`})}),`
`,e.jsx(n.h3,{children:"Filtered Search"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`# Search within specific source (⚠️ case-sensitive!)
request = SearchRequest(
    query="API documentation",
    filter=Filter(
        must=[
            FieldCondition(
                key="source_name",
                match=MatchValue(value="GitHub")  # Must match exactly
            )
        ]
    )
)

response = await client.collections.search_collection_advanced(
    readable_id="your-collection-id",
    search_request=request
)
`})}),`
`,e.jsx(n.h3,{children:"Date Range Filter"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from datetime import datetime, timezone, timedelta
from qdrant_client.http.models import DatetimeRange

# Find items from last 7 days
request = SearchRequest(
    query="bug fixes",
    filter=Filter(
        must=[
            FieldCondition(
                key="created_at",
                range=DatetimeRange(
                    gte=datetime.now(timezone.utc) - timedelta(days=7)
                )
            )
        ]
    )
)
`})}),`
`,e.jsx(n.h3,{children:"Case-Insensitive Source Matching"}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`from qdrant_client.http.models import MatchAny

# Handle different case variations
request = SearchRequest(
    query="deployment guide",
    filter=Filter(
        must=[
            FieldCondition(
                key="source_name",
                match=MatchAny(any=["GitHub", "github", "GITHUB"])
            )
        ]
    )
)
`})}),`
`,e.jsx(n.h3,{children:"REST API"}),`
`,e.jsx(t,{children:e.jsxs(n.p,{children:[`Try the advanced search endpoint with filters in our interactive API playground.
`,e.jsx(n.a,{href:"/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true",children:"Open API Explorer →"})]})}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-bash",children:`# GET - Basic search
curl -X GET "https://api.airweave.ai/collections/{id}/search?query=test" \\
  -H "x-api-key: your-api-key"

# POST - Advanced search with filters
curl -X POST "https://api.airweave.ai/collections/{id}/search" \\
  -H "x-api-key: your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "security vulnerabilities",
    "filter": {
      "must": [{
        "key": "source_name",
        "match": {"value": "GitHub"}
      }]
    },
    "score_threshold": 0.7
  }'
`})}),`
`,e.jsx(n.h3,{children:"Filter Patterns"}),`
`,e.jsx(n.p,{children:"This is a hypothetical example of what you might want to do."}),`
`,e.jsx(n.pre,{children:e.jsx(n.code,{className:"language-python",children:`# Multi-source search
FieldCondition(
    key="source_name",
    match=MatchAny(any=["Asana", "Jira", "Linear"])
)

# Priority filtering
FieldCondition(
    key="metadata.priority",
    match=MatchAny(any=["high", "critical", "P0"])
)

# Exclude resolved items
Filter(
    must_not=[
        FieldCondition(
            key="metadata.status",
            match=MatchAny(any=["closed", "resolved", "done"])
        )
    ]
)
`})}),`
`,e.jsx(n.h2,{children:"Learn More"}),`
`,e.jsxs(n.ul,{children:[`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:e.jsx(n.a,{href:"/search/concepts",children:"Search Concepts"})})," - Understand parameters and options"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:e.jsx(n.a,{href:"/search/filters",children:"Using Filters"})})," - Master Qdrant filtering"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:e.jsx(n.a,{href:"/api-reference/collections/search-collection-collections-readable-id-search-get",children:"API Reference"})})," - Complete API details"]}),`
`,e.jsxs(n.li,{children:[e.jsx(n.strong,{children:e.jsx(n.a,{href:"https://github.com/airweave-ai/airweave/blob/main/examples/04_advanced_search_with_filters.ipynb",children:"Interactive Tutorial ↗"})})," - Hands-on Jupyter notebook with visualizations"]}),`
`]})]})}function l(i={}){const{wrapper:n}={...a(),...i.components};return n?e.jsx(n,{...i,children:e.jsx(r,{...i})}):r(i)}function s(i,n){throw new Error("Expected component `"+i+"` to be defined: you likely forgot to import, pass, or provide it.")}export{l as default};
