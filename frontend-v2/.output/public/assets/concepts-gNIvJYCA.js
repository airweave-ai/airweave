import{j as e}from"./main-BEToz-TC.js";import{u as l}from"./use-docs-content-ogu5VP42.js";function i(n){const s={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",p:"p",pre:"pre",strong:"strong",table:"table",tbody:"tbody",td:"td",th:"th",thead:"thead",tr:"tr",ul:"ul",...l(),...n.components},{CodeGroup:r,Warning:t}=s;return r||d("CodeGroup"),t||d("Warning"),e.jsxs(e.Fragment,{children:[e.jsx(s.p,{children:"Airweave's search functionality enables you to query across all your connected data sources simultaneously. This unified search approach means you can find information whether it lives in GitHub, Slack, Asana, or any other integrated system—all through a single API call."}),`
`,e.jsx(s.h2,{children:"Core Concepts"}),`
`,e.jsx(s.h3,{children:"Query"}),`
`,e.jsx(s.p,{children:"The query is your search text—the question or keywords you're looking for across your data. Airweave uses semantic search, which means it understands the meaning behind your query, not just exact keyword matches."}),`
`,e.jsxs(r,{children:[e.jsx(s.pre,{children:e.jsx(s.code,{className:"language-text",children:`"What are our customer refund policies?"
"Show me recent security incidents"
"Find all discussions about Q4 planning"
`})}),e.jsx(s.pre,{children:e.jsx(s.code,{className:"language-text",children:`"payment gateway integration"
"user authentication flow"
"performance optimization"
`})}),e.jsx(s.pre,{children:e.jsx(s.code,{className:"language-text",children:`"customer complaints about shipping delays in the last month"
"technical debt in the authentication module"
"feature requests related to mobile app"
`})})]}),`
`,e.jsx(s.h3,{children:"Response Types"}),`
`,e.jsx(s.p,{children:"Airweave provides two response formats, each suited to different use cases:"}),`
`,e.jsxs(s.p,{children:[e.jsxs(s.strong,{children:["Raw Response (",e.jsx(s.code,{children:"raw"}),")"]}),": Returns the actual search results as structured data. Use this when you need to process results programmatically or display them in your own interface."]}),`
`,e.jsxs(s.p,{children:[e.jsxs(s.strong,{children:["Completion Response (",e.jsx(s.code,{children:"completion"}),")"]}),": Returns an AI-generated natural language answer based on the search results. The AI synthesizes information from multiple sources into a coherent response. Use this for conversational interfaces or when you need summarized insights."]}),`
`,e.jsx(s.h3,{children:"Query Expansion"}),`
`,e.jsx(s.p,{children:"Query expansion improves search recall by automatically generating related search terms. This helps find relevant content that might use different terminology than your original query."}),`
`,e.jsxs(s.table,{children:[e.jsx(s.thead,{children:e.jsxs(s.tr,{children:[e.jsx(s.th,{children:"Strategy"}),e.jsx(s.th,{children:"Description"}),e.jsx(s.th,{children:"Use Case"})]})}),e.jsxs(s.tbody,{children:[e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"auto"})}),e.jsx(s.td,{children:"Let Airweave decide whether to expand based on query complexity"}),e.jsx(s.td,{children:"Default choice for most searches"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"llm"})}),e.jsx(s.td,{children:"Uses language models to generate synonyms and related terms"}),e.jsx(s.td,{children:"Maximum recall for broad topics"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"no_expansion"})}),e.jsx(s.td,{children:"Searches only for the exact query"}),e.jsx(s.td,{children:"Precise searches or proper nouns"})]})]})]}),`
`,e.jsx(s.h3,{children:"Pagination"}),`
`,e.jsx(s.p,{children:"For searches returning many results, pagination controls help manage the response size:"}),`
`,e.jsxs(s.ul,{children:[`
`,e.jsxs(s.li,{children:[e.jsx(s.strong,{children:e.jsx(s.code,{children:"limit"})}),": Number of results per page (1-1000, default: 20)"]}),`
`,e.jsxs(s.li,{children:[e.jsx(s.strong,{children:e.jsx(s.code,{children:"offset"})}),": Number of results to skip (default: 0)"]}),`
`]}),`
`,e.jsx(s.pre,{children:e.jsx(s.code,{className:"language-python",children:`# Get the second page of 50 results
search_request = SearchRequest(
    query="project updates",
    limit=50,
    offset=50  # Skip first 50 results
)
`})}),`
`,e.jsx(t,{children:e.jsxs(s.p,{children:["When using query expansion (",e.jsx(s.code,{children:"auto"})," or ",e.jsx(s.code,{children:"llm"}),"), pagination may return inconsistent results across requests. For reliable pagination, set ",e.jsx(s.code,{children:'expansion_strategy="no_expansion"'}),"."]})}),`
`,e.jsx(s.h3,{children:"Score Threshold"}),`
`,e.jsx(s.p,{children:"The score threshold filters results by relevance score (0.0-1.0). Higher scores indicate better semantic matches. Setting a threshold helps eliminate marginally relevant results."}),`
`,e.jsx(s.pre,{children:e.jsx(s.code,{className:"language-python",children:`# Only return highly relevant results
search_request = SearchRequest(
    query="security vulnerabilities",
    score_threshold=0.7  # Only results with 70%+ relevance
)
`})}),`
`,e.jsx(s.h3,{children:"Summarization"}),`
`,e.jsx(s.p,{children:"When enabled, the summarization feature provides a concise overview of the search results. This is particularly useful when dealing with large result sets or when you need a quick understanding of the findings."}),`
`,e.jsx(s.h2,{children:"Quick Reference"}),`
`,e.jsxs(s.table,{children:[e.jsx(s.thead,{children:e.jsxs(s.tr,{children:[e.jsx(s.th,{children:"Parameter"}),e.jsx(s.th,{children:"Type"}),e.jsx(s.th,{children:"Default"}),e.jsx(s.th,{children:"Valid Range"}),e.jsx(s.th,{children:"Description"})]})}),e.jsxs(s.tbody,{children:[e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"query"})}),e.jsx(s.td,{children:"string"}),e.jsx(s.td,{children:"required"}),e.jsx(s.td,{children:"1-1000 chars"}),e.jsx(s.td,{children:"Search text"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"response_type"})}),e.jsx(s.td,{children:"enum"}),e.jsx(s.td,{children:e.jsx(s.code,{children:"raw"})}),e.jsxs(s.td,{children:[e.jsx(s.code,{children:"raw"}),", ",e.jsx(s.code,{children:"completion"})]}),e.jsx(s.td,{children:"Response format"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"expansion_strategy"})}),e.jsx(s.td,{children:"enum"}),e.jsx(s.td,{children:e.jsx(s.code,{children:"auto"})}),e.jsxs(s.td,{children:[e.jsx(s.code,{children:"auto"}),", ",e.jsx(s.code,{children:"llm"}),", ",e.jsx(s.code,{children:"no_expansion"})]}),e.jsx(s.td,{children:"Query expansion method"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"limit"})}),e.jsx(s.td,{children:"integer"}),e.jsx(s.td,{children:"20"}),e.jsx(s.td,{children:"1-1000"}),e.jsx(s.td,{children:"Results per page"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"offset"})}),e.jsx(s.td,{children:"integer"}),e.jsx(s.td,{children:"0"}),e.jsx(s.td,{children:"≥ 0"}),e.jsx(s.td,{children:"Results to skip"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"score_threshold"})}),e.jsx(s.td,{children:"float"}),e.jsx(s.td,{children:"none"}),e.jsx(s.td,{children:"0.0-1.0"}),e.jsx(s.td,{children:"Minimum relevance score"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"summarize"})}),e.jsx(s.td,{children:"boolean"}),e.jsx(s.td,{children:"false"}),e.jsx(s.td,{children:"-"}),e.jsx(s.td,{children:"Enable result summarization"})]}),e.jsxs(s.tr,{children:[e.jsx(s.td,{children:e.jsx(s.code,{children:"filter"})}),e.jsx(s.td,{children:"object"}),e.jsx(s.td,{children:"none"}),e.jsx(s.td,{children:"-"}),e.jsx(s.td,{children:"Qdrant filter object"})]})]})]}),`
`,e.jsx(s.h2,{children:"Next Steps"}),`
`,e.jsxs(s.ul,{children:[`
`,e.jsxs(s.li,{children:["Learn about ",e.jsx(s.a,{href:"/search/filters",children:"filtering search results"})," to narrow down results by metadata"]}),`
`,e.jsxs(s.li,{children:["Explore ",e.jsx(s.a,{href:"/search/examples",children:"practical examples"})," of search queries"]}),`
`,e.jsxs(s.li,{children:[e.jsx(s.strong,{children:e.jsx(s.a,{href:"/api-reference/collections/search-collection-collections-readable-id-search-get",children:"API Reference"})})," - Complete API details"]}),`
`]})]})}function o(n={}){const{wrapper:s}={...l(),...n.components};return s?e.jsx(s,{...n,children:e.jsx(i,{...n})}):i(n)}function d(n,s){throw new Error("Expected component `"+n+"` to be defined: you likely forgot to import, pass, or provide it.")}export{o as default};
