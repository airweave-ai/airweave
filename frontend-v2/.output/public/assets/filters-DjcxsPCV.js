import{j as n}from"./main-BEToz-TC.js";import{u as a}from"./use-docs-content-ogu5VP42.js";function s(i){const e={a:"a",code:"code",h2:"h2",h3:"h3",li:"li",p:"p",pre:"pre",strong:"strong",ul:"ul",...a(),...i.components},{Tip:t}=e;return t||r("Tip"),n.jsxs(n.Fragment,{children:[n.jsx(e.p,{children:"While vector search excels at finding semantically similar content, filters allow you to narrow results based on exact payload criteria. This combination of semantic search and filtering makes Airweave particularly powerful for finding specific information within large datasets."}),`
`,n.jsx(e.h2,{children:"Why Filters Matter"}),`
`,n.jsx(e.p,{children:'Consider searching for "payment processing issues" across your connected systems. Without filters, you might get results from three years ago, from test environments, or from unrelated payment systems. Filters let you specify exactly which subset of data to search within.'}),`
`,n.jsx(e.h2,{children:"Filter Structure"}),`
`,n.jsx(e.p,{children:"Airweave uses Qdrant's filtering system, which provides a flexible way to express complex conditions. Filters consist of conditions combined with logical operators."}),`
`,n.jsxs(t,{children:[n.jsx(e.p,{children:"Try these filter examples in our interactive API playground."}),n.jsx(e.p,{children:n.jsx(e.a,{href:"/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true",children:"Open API Explorer →"})})]}),`
`,n.jsx(e.h3,{children:"Basic Filter Anatomy"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`from qdrant_client.http.models import Filter, FieldCondition, MatchValue

filter = Filter(
    must=[
        FieldCondition(
            key="source_name",
            match=MatchValue(value="Stripe")
        )
    ]
)
`})}),`
`,n.jsx(e.h2,{children:"Logical Operators"}),`
`,n.jsx(e.p,{children:"Filters support three logical operators that can be combined to create complex queries:"}),`
`,n.jsx(e.h3,{children:"Must (AND)"}),`
`,n.jsxs(e.p,{children:["All conditions in the ",n.jsx(e.code,{children:"must"})," array must be satisfied. Think of this as an AND operation."]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`Filter(
    must=[
        FieldCondition(key="source_name", match=MatchValue(value="GitHub")),
        FieldCondition(key="is_archived", match=MatchValue(value=False))
    ]
)
# Returns: GitHub items that are NOT archived
`})}),`
`,n.jsx(e.h3,{children:"Should (OR)"}),`
`,n.jsxs(e.p,{children:["At least one condition in the ",n.jsx(e.code,{children:"should"})," array must be satisfied. This creates an OR operation."]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`Filter(
    should=[
        FieldCondition(key="priority", match=MatchValue(value="high")),
        FieldCondition(key="priority", match=MatchValue(value="critical"))
    ]
)
# Returns: Items with high OR critical priority
`})}),`
`,n.jsx(e.h3,{children:"Must Not (NOT)"}),`
`,n.jsxs(e.p,{children:["None of the conditions in the ",n.jsx(e.code,{children:"must_not"})," array can be satisfied. Use this to exclude results."]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`Filter(
    must_not=[
        FieldCondition(key="status", match=MatchValue(value="resolved"))
    ]
)
# Returns: All items except those with resolved status
`})}),`
`,n.jsx(e.h2,{children:"Common Airweave Fields"}),`
`,n.jsx(e.p,{children:"Understanding the available fields is crucial for effective filtering. Here are the most commonly used fields across Airweave data sources:"}),`
`,n.jsxs(e.h3,{children:[n.jsx(e.code,{children:"source_name"})," field"]}),`
`,n.jsxs(e.p,{children:["The data source identifier. ",n.jsx(e.strong,{children:"Important"}),": This field is case-sensitive."]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`# Correct - matches exactly
FieldCondition(key="source_name", match=MatchValue(value="Asana"))

# Incorrect - won't match "Asana"
FieldCondition(key="source_name", match=MatchValue(value="asana"))
`})}),`
`,n.jsx(e.h3,{children:"Timestamps"}),`
`,n.jsxs(e.p,{children:["Timestamps use ISO 8601 format. Use ",n.jsx(e.code,{children:"DatetimeRange"})," for date filtering:"]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`from qdrant_client.http.models import DatetimeRange
from datetime import datetime, timezone

FieldCondition(
    key="created_at",
    range=DatetimeRange(
        gte=datetime(2024, 1, 1, tzinfo=timezone.utc),
        lte=datetime(2024, 12, 31, tzinfo=timezone.utc)
    )
)
`})}),`
`,n.jsx(e.h3,{children:"Nested Payload"}),`
`,n.jsx(e.p,{children:"Nested fields can be accessed using dot notation:"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`# Access nested metadata fields
FieldCondition(key="metadata.project_id", match=MatchValue(value="PROJ-123"))
FieldCondition(key="metadata.assignee", match=MatchValue(value="john@example.com"))
`})}),`
`,n.jsx(e.h2,{children:"Practical Examples"}),`
`,n.jsx(e.h3,{children:"Filter by Source"}),`
`,n.jsx(e.p,{children:"Find all content from a specific data source:"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`search_request = SearchRequest(
    query="deployment procedures",
    filter=Filter(
        must=[
            FieldCondition(
                key="source_name",
                match=MatchValue(value="Confluence")
            )
        ]
    )
)
`})}),`
`,n.jsx(e.h3,{children:"Date Range Filtering"}),`
`,n.jsx(e.p,{children:"Find recent items within the last 30 days:"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`from datetime import datetime, timedelta, timezone

thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

search_request = SearchRequest(
    query="bug reports",
    filter=Filter(
        must=[
            FieldCondition(
                key="created_at",
                range=DatetimeRange(gte=thirty_days_ago)
            )
        ]
    )
)
`})}),`
`,n.jsx(e.h3,{children:"Complex Multi-Source Query"}),`
`,n.jsx(e.p,{children:"Find high-priority items from multiple support systems:"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`from qdrant_client.http.models import MatchAny

search_request = SearchRequest(
    query="customer complaints",
    filter=Filter(
        must=[
            FieldCondition(
                key="source_name",
                match=MatchAny(any=["Zendesk", "Intercom"])
            ),
            FieldCondition(
                key="priority",
                match=MatchValue(value="high")
            )
        ],
        must_not=[
            FieldCondition(
                key="status",
                match=MatchValue(value="closed")
            )
        ]
    )
)
`})}),`
`,n.jsx(e.h3,{children:"Handling Case Sensitivity"}),`
`,n.jsxs(e.p,{children:["Since ",n.jsx(e.code,{children:"source_name"})," is case-sensitive, use ",n.jsx(e.code,{children:"MatchAny"})," to handle variations:"]}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`# Case-insensitive source matching
FieldCondition(
    key="source_name",
    match=MatchAny(any=["Slack", "slack", "SLACK"])
)
`})}),`
`,n.jsx(e.h2,{children:"Advanced Filtering"}),`
`,n.jsx(e.h3,{children:"Combining Conditions"}),`
`,n.jsx(e.p,{children:"Create sophisticated filters by nesting conditions:"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`Filter(
    must=[
        FieldCondition(key="source_name", match=MatchValue(value="GitHub")),
        Filter(
            should=[
                FieldCondition(key="labels", match=MatchAny(any=["bug", "critical"])),
                FieldCondition(key="assignee", match=MatchValue(value="unassigned"))
            ]
        )
    ]
)
# Returns: GitHub issues that are either labeled as bug/critical OR unassigned
`})}),`
`,n.jsx(e.h3,{children:"Null and Empty Checks"}),`
`,n.jsx(e.p,{children:"Check for missing or empty fields:"}),`
`,n.jsx(e.pre,{children:n.jsx(e.code,{className:"language-python",children:`from qdrant_client.http.models import IsNullCondition, IsEmptyCondition

# Find items without an assignee
Filter(
    must=[
        IsNullCondition(is_null={"key": "assignee"})
    ]
)

# Find items with empty tags array
Filter(
    must=[
        IsEmptyCondition(key="tags")
    ]
)
`})}),`
`,n.jsx(e.h2,{children:"Next Steps"}),`
`,n.jsxs(e.ul,{children:[`
`,n.jsxs(e.li,{children:["Explore ",n.jsx(e.a,{href:"https://github.com/airweave-ai/airweave/tree/main/examples/04_advanced_search_with_filters.ipynb",children:"search examples"})," with real-world filtering scenarios"]}),`
`,n.jsxs(e.li,{children:["Review the ",n.jsx(e.a,{href:"/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true",children:"API reference"})," for complete filter specifications"]}),`
`,n.jsxs(e.li,{children:["Learn about ",n.jsx(e.a,{href:"/search/concepts",children:"search concepts"})," for a comprehensive understanding"]}),`
`]})]})}function o(i={}){const{wrapper:e}={...a(),...i.components};return e?n.jsx(e,{...i,children:n.jsx(s,{...i})}):s(i)}function r(i,e){throw new Error("Expected component `"+i+"` to be defined: you likely forgot to import, pass, or provide it.")}export{o as default};
