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
      children: "This page provides quick examples to get you started with Airweave search. For a comprehensive, hands-on tutorial with visualizations and real-world scenarios, check out our interactive Jupyter notebook."
    }), "\n", jsxs(Tip, {
      title: "Interactive Tutorial",
      children: [jsx(_components.p, {
        children: "Learn search concepts through hands-on examples in our comprehensive Jupyter notebook with live code, visualizations, and real-world scenarios."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://github.com/airweave-ai/airweave/blob/main/examples/04_advanced_search_with_filters.ipynb",
          children: "View the Advanced Search Tutorial →"
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Quick Start"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from airweave import AirweaveSDK\nfrom airweave.schemas.search import SearchRequest\nfrom qdrant_client.http.models import Filter, FieldCondition, MatchValue\n\nclient = AirweaveSDK(api_key="your-api-key")\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Essential Examples"
    }), "\n", jsx(_components.h3, {
      children: "Basic Search"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Simple text search\nresponse = await client.collections.search_collection(\n    readable_id="your-collection-id",\n    query="customer onboarding process"\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Search with AI Completion"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Get AI-generated insights\nresponse = await client.collections.search_collection(\n    readable_id="your-collection-id",\n    query="What are our security policies?",\n    response_type="completion"\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Filtered Search"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Search within specific source (⚠️ case-sensitive!)\nrequest = SearchRequest(\n    query="API documentation",\n    filter=Filter(\n        must=[\n            FieldCondition(\n                key="source_name",\n                match=MatchValue(value="GitHub")  # Must match exactly\n            )\n        ]\n    )\n)\n\nresponse = await client.collections.search_collection_advanced(\n    readable_id="your-collection-id",\n    search_request=request\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Date Range Filter"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from datetime import datetime, timezone, timedelta\nfrom qdrant_client.http.models import DatetimeRange\n\n# Find items from last 7 days\nrequest = SearchRequest(\n    query="bug fixes",\n    filter=Filter(\n        must=[\n            FieldCondition(\n                key="created_at",\n                range=DatetimeRange(\n                    gte=datetime.now(timezone.utc) - timedelta(days=7)\n                )\n            )\n        ]\n    )\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Case-Insensitive Source Matching"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from qdrant_client.http.models import MatchAny\n\n# Handle different case variations\nrequest = SearchRequest(\n    query="deployment guide",\n    filter=Filter(\n        must=[\n            FieldCondition(\n                key="source_name",\n                match=MatchAny(any=["GitHub", "github", "GITHUB"])\n            )\n        ]\n    )\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "REST API"
    }), "\n", jsx(Tip, {
      children: jsxs(_components.p, {
        children: ["Try the advanced search endpoint with filters in our interactive API playground.\n", jsx(_components.a, {
          href: "/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true",
          children: "Open API Explorer →"
        })]
      })
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-bash",
        children: `# GET - Basic search
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
`
      })
    }), "\n", jsx(_components.h3, {
      children: "Filter Patterns"
    }), "\n", jsx(_components.p, {
      children: "This is a hypothetical example of what you might want to do."
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Multi-source search\nFieldCondition(\n    key="source_name",\n    match=MatchAny(any=["Asana", "Jira", "Linear"])\n)\n\n# Priority filtering\nFieldCondition(\n    key="metadata.priority",\n    match=MatchAny(any=["high", "critical", "P0"])\n)\n\n# Exclude resolved items\nFilter(\n    must_not=[\n        FieldCondition(\n            key="metadata.status",\n            match=MatchAny(any=["closed", "resolved", "done"])\n        )\n    ]\n)\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Learn More"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.a, {
            href: "/search/concepts",
            children: "Search Concepts"
          })
        }), " - Understand parameters and options"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.a, {
            href: "/search/filters",
            children: "Using Filters"
          })
        }), " - Master Qdrant filtering"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.a, {
            href: "/api-reference/collections/search-collection-collections-readable-id-search-get",
            children: "API Reference"
          })
        }), " - Complete API details"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.a, {
            href: "https://github.com/airweave-ai/airweave/blob/main/examples/04_advanced_search_with_filters.ipynb",
            children: "Interactive Tutorial ↗"
          })
        }), " - Hands-on Jupyter notebook with visualizations"]
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
