import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { u as useMDXComponents } from "./use-docs-content-CQG4H0bA.mjs";
import "@tanstack/react-query";
import "react";
import "./router-BGxBdlkD.mjs";
import "@tanstack/react-router";
import "@tanstack/react-query-persist-client";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-dialog";
import "@radix-ui/react-tooltip";
import "zustand";
import "zustand/middleware";
import "@radix-ui/react-avatar";
import "@radix-ui/react-dropdown-menu";
import "cmdk";
import "sonner";
import "idb-keyval";
function _createMdxContent(props) {
  const _components = {
    a: "a",
    code: "code",
    h2: "h2",
    h3: "h3",
    li: "li",
    p: "p",
    pre: "pre",
    strong: "strong",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Tip } = _components;
  if (!Tip) _missingMdxReference("Tip");
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "While vector search excels at finding semantically similar content, filters allow you to narrow results based on exact payload criteria. This combination of semantic search and filtering makes Airweave particularly powerful for finding specific information within large datasets."
    }), "\n", jsx(_components.h2, {
      children: "Why Filters Matter"
    }), "\n", jsx(_components.p, {
      children: 'Consider searching for "payment processing issues" across your connected systems. Without filters, you might get results from three years ago, from test environments, or from unrelated payment systems. Filters let you specify exactly which subset of data to search within.'
    }), "\n", jsx(_components.h2, {
      children: "Filter Structure"
    }), "\n", jsx(_components.p, {
      children: "Airweave uses Qdrant's filtering system, which provides a flexible way to express complex conditions. Filters consist of conditions combined with logical operators."
    }), "\n", jsxs(Tip, {
      children: [jsx(_components.p, {
        children: "Try these filter examples in our interactive API playground."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true",
          children: "Open API Explorer →"
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Basic Filter Anatomy"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from qdrant_client.http.models import Filter, FieldCondition, MatchValue\n\nfilter = Filter(\n    must=[\n        FieldCondition(\n            key="source_name",\n            match=MatchValue(value="Stripe")\n        )\n    ]\n)\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Logical Operators"
    }), "\n", jsx(_components.p, {
      children: "Filters support three logical operators that can be combined to create complex queries:"
    }), "\n", jsx(_components.h3, {
      children: "Must (AND)"
    }), "\n", jsxs(_components.p, {
      children: ["All conditions in the ", jsx(_components.code, {
        children: "must"
      }), " array must be satisfied. Think of this as an AND operation."]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'Filter(\n    must=[\n        FieldCondition(key="source_name", match=MatchValue(value="GitHub")),\n        FieldCondition(key="is_archived", match=MatchValue(value=False))\n    ]\n)\n# Returns: GitHub items that are NOT archived\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Should (OR)"
    }), "\n", jsxs(_components.p, {
      children: ["At least one condition in the ", jsx(_components.code, {
        children: "should"
      }), " array must be satisfied. This creates an OR operation."]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'Filter(\n    should=[\n        FieldCondition(key="priority", match=MatchValue(value="high")),\n        FieldCondition(key="priority", match=MatchValue(value="critical"))\n    ]\n)\n# Returns: Items with high OR critical priority\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Must Not (NOT)"
    }), "\n", jsxs(_components.p, {
      children: ["None of the conditions in the ", jsx(_components.code, {
        children: "must_not"
      }), " array can be satisfied. Use this to exclude results."]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'Filter(\n    must_not=[\n        FieldCondition(key="status", match=MatchValue(value="resolved"))\n    ]\n)\n# Returns: All items except those with resolved status\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Common Airweave Fields"
    }), "\n", jsx(_components.p, {
      children: "Understanding the available fields is crucial for effective filtering. Here are the most commonly used fields across Airweave data sources:"
    }), "\n", jsxs(_components.h3, {
      children: [jsx(_components.code, {
        children: "source_name"
      }), " field"]
    }), "\n", jsxs(_components.p, {
      children: ["The data source identifier. ", jsx(_components.strong, {
        children: "Important"
      }), ": This field is case-sensitive."]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: `# Correct - matches exactly
FieldCondition(key="source_name", match=MatchValue(value="Asana"))

# Incorrect - won't match "Asana"
FieldCondition(key="source_name", match=MatchValue(value="asana"))
`
      })
    }), "\n", jsx(_components.h3, {
      children: "Timestamps"
    }), "\n", jsxs(_components.p, {
      children: ["Timestamps use ISO 8601 format. Use ", jsx(_components.code, {
        children: "DatetimeRange"
      }), " for date filtering:"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from qdrant_client.http.models import DatetimeRange\nfrom datetime import datetime, timezone\n\nFieldCondition(\n    key="created_at",\n    range=DatetimeRange(\n        gte=datetime(2024, 1, 1, tzinfo=timezone.utc),\n        lte=datetime(2024, 12, 31, tzinfo=timezone.utc)\n    )\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Nested Payload"
    }), "\n", jsx(_components.p, {
      children: "Nested fields can be accessed using dot notation:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Access nested metadata fields\nFieldCondition(key="metadata.project_id", match=MatchValue(value="PROJ-123"))\nFieldCondition(key="metadata.assignee", match=MatchValue(value="john@example.com"))\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Practical Examples"
    }), "\n", jsx(_components.h3, {
      children: "Filter by Source"
    }), "\n", jsx(_components.p, {
      children: "Find all content from a specific data source:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'search_request = SearchRequest(\n    query="deployment procedures",\n    filter=Filter(\n        must=[\n            FieldCondition(\n                key="source_name",\n                match=MatchValue(value="Confluence")\n            )\n        ]\n    )\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Date Range Filtering"
    }), "\n", jsx(_components.p, {
      children: "Find recent items within the last 30 days:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from datetime import datetime, timedelta, timezone\n\nthirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)\n\nsearch_request = SearchRequest(\n    query="bug reports",\n    filter=Filter(\n        must=[\n            FieldCondition(\n                key="created_at",\n                range=DatetimeRange(gte=thirty_days_ago)\n            )\n        ]\n    )\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Complex Multi-Source Query"
    }), "\n", jsx(_components.p, {
      children: "Find high-priority items from multiple support systems:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from qdrant_client.http.models import MatchAny\n\nsearch_request = SearchRequest(\n    query="customer complaints",\n    filter=Filter(\n        must=[\n            FieldCondition(\n                key="source_name",\n                match=MatchAny(any=["Zendesk", "Intercom"])\n            ),\n            FieldCondition(\n                key="priority",\n                match=MatchValue(value="high")\n            )\n        ],\n        must_not=[\n            FieldCondition(\n                key="status",\n                match=MatchValue(value="closed")\n            )\n        ]\n    )\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Handling Case Sensitivity"
    }), "\n", jsxs(_components.p, {
      children: ["Since ", jsx(_components.code, {
        children: "source_name"
      }), " is case-sensitive, use ", jsx(_components.code, {
        children: "MatchAny"
      }), " to handle variations:"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Case-insensitive source matching\nFieldCondition(\n    key="source_name",\n    match=MatchAny(any=["Slack", "slack", "SLACK"])\n)\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Advanced Filtering"
    }), "\n", jsx(_components.h3, {
      children: "Combining Conditions"
    }), "\n", jsx(_components.p, {
      children: "Create sophisticated filters by nesting conditions:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'Filter(\n    must=[\n        FieldCondition(key="source_name", match=MatchValue(value="GitHub")),\n        Filter(\n            should=[\n                FieldCondition(key="labels", match=MatchAny(any=["bug", "critical"])),\n                FieldCondition(key="assignee", match=MatchValue(value="unassigned"))\n            ]\n        )\n    ]\n)\n# Returns: GitHub issues that are either labeled as bug/critical OR unassigned\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Null and Empty Checks"
    }), "\n", jsx(_components.p, {
      children: "Check for missing or empty fields:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from qdrant_client.http.models import IsNullCondition, IsEmptyCondition\n\n# Find items without an assignee\nFilter(\n    must=[\n        IsNullCondition(is_null={"key": "assignee"})\n    ]\n)\n\n# Find items with empty tags array\nFilter(\n    must=[\n        IsEmptyCondition(key="tags")\n    ]\n)\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Next Steps"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: ["Explore ", jsx(_components.a, {
          href: "https://github.com/airweave-ai/airweave/tree/main/examples/04_advanced_search_with_filters.ipynb",
          children: "search examples"
        }), " with real-world filtering scenarios"]
      }), "\n", jsxs(_components.li, {
        children: ["Review the ", jsx(_components.a, {
          href: "/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true",
          children: "API reference"
        }), " for complete filter specifications"]
      }), "\n", jsxs(_components.li, {
        children: ["Learn about ", jsx(_components.a, {
          href: "/search/concepts",
          children: "search concepts"
        }), " for a comprehensive understanding"]
      }), "\n"]
    })]
  });
}
function MDXContent(props = {}) {
  const { wrapper: MDXLayout } = {
    ...useMDXComponents(),
    ...props.components
  };
  return MDXLayout ? jsx(MDXLayout, {
    ...props,
    children: jsx(_createMdxContent, {
      ...props
    })
  }) : _createMdxContent(props);
}
function _missingMdxReference(id, component) {
  throw new Error("Expected component `" + id + "` to be defined: you likely forgot to import, pass, or provide it.");
}
export {
  MDXContent as default
};
