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
    del: "del",
    em: "em",
    h2: "h2",
    h3: "h3",
    li: "li",
    ol: "ol",
    p: "p",
    pre: "pre",
    strong: "strong",
    table: "table",
    tbody: "tbody",
    td: "td",
    th: "th",
    thead: "thead",
    tr: "tr",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Accordion, Card, CardGroup, CodeBlocks, CodeGroup, Note, Tip, Warning } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
  if (!Card) _missingMdxReference("Card");
  if (!CardGroup) _missingMdxReference("CardGroup");
  if (!CodeBlocks) _missingMdxReference("CodeBlocks");
  if (!CodeGroup) _missingMdxReference("CodeGroup");
  if (!Note) _missingMdxReference("Note");
  if (!Tip) _missingMdxReference("Tip");
  if (!Warning) _missingMdxReference("Warning");
  return jsxs(Fragment, {
    children: [jsxs(Warning, {
      children: [jsx(_components.p, {
        children: jsx(_components.strong, {
          children: "Search API Updated (October 2025)"
        })
      }), jsx(_components.p, {
        children: "The search API has been updated. The legacy API continues to work, but we recommend migrating to the new API."
      }), jsxs(Accordion, {
        title: "View Migration Details",
        children: [jsx(_components.h3, {
          children: "What Changed?"
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Endpoints:"
          })
        }), jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.del, {
              children: jsx(_components.code, {
                children: "GET /collections/{id}/search"
              })
            }), " → Still works but deprecated"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "POST /collections/{id}/search"
            }), " → Accepts both old and new schemas"]
          }), "\n"]
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Request Schema:"
          })
        }), jsxs(_components.table, {
          children: [jsx(_components.thead, {
            children: jsxs(_components.tr, {
              children: [jsx(_components.th, {
                children: "Legacy Field"
              }), jsx(_components.th, {
                children: "New Field"
              }), jsx(_components.th, {
                children: "Change"
              })]
            })
          }), jsxs(_components.tbody, {
            children: [jsxs(_components.tr, {
              children: [jsxs(_components.td, {
                children: [jsx(_components.code, {
                  children: "response_type"
                }), " (", jsx(_components.code, {
                  children: '"raw"'
                }), " | ", jsx(_components.code, {
                  children: '"completion"'
                }), ")"]
              }), jsxs(_components.td, {
                children: [jsx(_components.code, {
                  children: "generate_answer"
                }), " (boolean)"]
              }), jsx(_components.td, {
                children: "Enum → Boolean"
              })]
            }), jsxs(_components.tr, {
              children: [jsxs(_components.td, {
                children: [jsx(_components.code, {
                  children: "expansion_strategy"
                }), " (", jsx(_components.code, {
                  children: '"auto"'
                }), " | ", jsx(_components.code, {
                  children: '"llm"'
                }), " | ", jsx(_components.code, {
                  children: '"no_expansion"'
                }), ")"]
              }), jsxs(_components.td, {
                children: [jsx(_components.code, {
                  children: "expand_query"
                }), " (boolean)"]
              }), jsx(_components.td, {
                children: "Enum → Boolean"
              })]
            }), jsxs(_components.tr, {
              children: [jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "enable_query_interpretation"
                })
              }), jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "interpret_filters"
                })
              }), jsx(_components.td, {
                children: "Renamed"
              })]
            }), jsxs(_components.tr, {
              children: [jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "search_method"
                })
              }), jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "retrieval_strategy"
                })
              }), jsx(_components.td, {
                children: "Renamed"
              })]
            }), jsxs(_components.tr, {
              children: [jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "recency_bias"
                })
              }), jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "temporal_relevance"
                })
              }), jsx(_components.td, {
                children: "Renamed"
              })]
            }), jsxs(_components.tr, {
              children: [jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "enable_reranking"
                })
              }), jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "rerank"
                })
              }), jsx(_components.td, {
                children: "Renamed"
              })]
            }), jsxs(_components.tr, {
              children: [jsx(_components.td, {
                children: jsx(_components.code, {
                  children: "score_threshold"
                })
              }), jsx(_components.td, {
                children: jsx(_components.em, {
                  children: "(removed)"
                })
              }), jsx(_components.td, {
                children: "Deprecated"
              })]
            })]
          })]
        }), jsx(_components.h3, {
          children: "Full Comparison"
        }), jsxs(CodeGroup, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'from airweave import AirweaveSDK\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\n# Old GET endpoint with query params\nresponse = await client.collections.search_collection(\n    readable_id="my-collection",\n    query="customer issues",\n    response_type="completion",  # ❌\n    limit=50,\n    recency_bias=0.5,\n)\n\n# Old POST with verbose schema\nfrom airweave.schemas.search import SearchRequest\n\nrequest = SearchRequest(\n    query="deployment procedures",\n    response_type="completion",           # ❌\n    expansion_strategy="auto",            # ❌\n    enable_reranking=True,                # ✅\n    enable_query_interpretation=True,     # ❌\n    search_method="hybrid",               # ❌\n    recency_bias=0.3,                     # ❌\n)\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'from airweave import AirweaveSDK\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\n# New POST-only endpoint with clean schema\nfrom airweave.schemas.search import SearchRequest\n\nrequest = SearchRequest(\n    query="customer issues",\n    generate_answer=True,         # ✅\n    limit=50,\n    temporal_relevance=0.5,       # ✅\n)\n\nresponse = await client.collections.search_collection(\n    readable_id="my-collection",\n    search_request=request\n)\n\n# Comprehensive example\nrequest = SearchRequest(\n    query="deployment procedures",\n    generate_answer=True,         # ✅\n    expand_query=True,            # ✅\n    rerank=True,                  # ✅\n    interpret_filters=True,       # ✅\n    retrieval_strategy="hybrid",  # ✅\n    temporal_relevance=0.3,       # ✅\n)\n'
            })
          })]
        }), jsx(_components.h2, {
          children: "Migration Steps"
        }), jsx(_components.h3, {
          children: "Step 1: Update Request Schema"
        }), jsxs(CodeGroup, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'request = SearchRequest(\n    query="test",\n    response_type="completion",\n    expansion_strategy="auto",\n    enable_reranking=True,\n    search_method="hybrid",\n)\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'request = SearchRequest(\n    query="test",\n    generate_answer=True,\n    expand_query=True,\n    rerank=True,\n    retrieval_strategy="hybrid",\n)\n'
            })
          })]
        }), jsx(_components.h3, {
          children: "Step 2: Update Response Handling"
        }), jsxs(CodeGroup, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'response = await client.collections.search_collection(...)\n\n# Old response structure\nif response.status == "success":\n    if response.response_type == "completion":\n        print(response.completion)\n    else:\n        print(response.results)\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: "response = await client.collections.search_collection(...)\n\n# New response structure\nif response.completion:\n    print(response.completion)\nelse:\n    print(response.results)\n"
            })
          })]
        }), jsx(_components.h3, {
          children: "Step 3: Remove Deprecated Fields"
        }), jsx(_components.p, {
          children: "The new response no longer includes:"
        }), jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "status"
            }), " field"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "response_type"
            }), " field"]
          }), "\n"]
        }), jsx(_components.h2, {
          children: "REST API Migration"
        }), jsx(_components.h3, {
          children: "GET Endpoint (Deprecated)"
        }), jsxs(CodeGroup, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: 'curl -X GET "https://api.airweave.ai/collections/{id}/search?query=test&response_type=completion" \\\n  -H "x-api-key: your-api-key"\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: `curl -X POST "https://api.airweave.ai/collections/{id}/search" \\
  -H "x-api-key: your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "test",
    "generate_answer": true
  }'
`
            })
          })]
        }), jsx(_components.h3, {
          children: "POST Endpoint Schema"
        }), jsxs(CodeGroup, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: '{\n  "query": "test",\n  "response_type": "completion",\n  "expansion_strategy": "auto",\n  "enable_reranking": true,\n  "search_method": "hybrid"\n}\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: '{\n  "query": "test",\n  "generate_answer": true,\n  "expand_query": true,\n  "rerank": true,\n  "retrieval_strategy": "hybrid"\n}\n'
            })
          })]
        }), jsx(_components.h3, {
          children: "Detecting Deprecation"
        }), jsx(_components.p, {
          children: "When using the legacy API, you'll receive HTTP headers indicating deprecation:"
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-http",
            children: "X-API-Deprecation: true\nX-API-Deprecation-Message: ...\n"
          })
        })]
      })]
    }), "\n", jsx(_components.p, {
      children: "Airweave lets you search across all your connected data sources through one unified interface. When you query a collection, Airweave runs a multi-step search pipeline that combines AI understanding with keyword precision. You can start with the defaults or configure each step for full control."
    }), "\n", jsx(Note, {
      children: jsxs(_components.p, {
        children: ["Want to try out our search right now? Head to our ", jsx(_components.a, {
          href: "https://docs.airweave.ai/api-reference/collections/search-collections-readable-id-search-post",
          children: "interactive API documentation"
        }), " where you can test search queries directly in your browser!"]
      })
    }), "\n", jsx(_components.h2, {
      children: "Quick Reference"
    }), "\n", jsx(_components.p, {
      children: "Here are the default settings Airweave uses. You can override any of these in your queries."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Default"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "expand_query"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "true"
            })
          }), jsx(_components.td, {
            children: "Generate query variations for better recall"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "retrieval_strategy"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "hybrid"
            })
          }), jsx(_components.td, {
            children: "Combines AI semantic search with keyword matching"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "interpret_filters"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "false"
            })
          }), jsx(_components.td, {
            children: "Extract filters from natural language (you control manually by default)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "rerank"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "true"
            })
          }), jsx(_components.td, {
            children: "LLM-based result reordering (adds ~10s latency)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "temporal_relevance"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "0.3"
            })
          }), jsx(_components.td, {
            children: "Weight toward recent content (0.0-1.0)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "generate_answer"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "true"
            })
          }), jsx(_components.td, {
            children: "Generate AI completion from results"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "limit"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "1000"
            })
          }), jsx(_components.td, {
            children: "Maximum results to return"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "offset"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "0"
            })
          }), jsx(_components.td, {
            children: "Results to skip for pagination"
          })]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Which endpoint to use"
    }), "\n", jsxs(CardGroup, {
      cols: 2,
      children: [jsxs(Card, {
        title: "Simple Search (Deprecated)",
        icon: "magnifying-glass",
        href: "/api-reference/collections/search-collections-readable-id-search-get",
        children: [jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "GET"
          }), " ", jsx(_components.code, {
            children: "/collections/{readable_id}/search"
          })]
        }), jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "⚠️ Deprecated:"
          }), " This endpoint is maintained for backwards compatibility only. Use POST for new integrations."]
        })]
      }), jsxs(Card, {
        title: "Advanced Search (Recommended)",
        icon: "sliders",
        href: "/api-reference/collections/search-collections-readable-id-search-post",
        children: [jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "POST"
          }), " ", jsx(_components.code, {
            children: "/collections/{readable_id}/search"
          })]
        }), jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Recommended:"
          }), " Full control. Use this for all new integrations."]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "How Airweave search works"
    }), "\n", jsx(_components.p, {
      children: "Each search runs through a multi step pipeline. Understanding the stages helps explain why different parameters exist and when to use them:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Query expansion"
        }), ": Generate variations of the user query to capture synonyms and related terms."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Retrieval"
        }), ": Use keyword, neural, or hybrid methods to fetch candidate documents."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Filtering"
        }), ": Apply structured metadata filters before or during retrieval."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Recency bias"
        }), ": Optionally weight results toward fresher content."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Reranking"
        }), ": Use AI to reorder the top results for higher precision."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Answer generation"
        }), ": Return raw documents or synthesize a natural language response."]
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "Defaults are designed to work out of the box, and you can override any stage as needed."
    }), "\n", jsx(_components.h2, {
      children: "Parameters"
    }), "\n", jsx(_components.h3, {
      children: "Query Expansion"
    }), "\n", jsx(_components.p, {
      children: "Expands your query to catch related terms and synonyms that may not appear verbatim in your documents. This improves recall when wording differs but meaning is the same."
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "expand_query"
      }), " (boolean)"]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "true"
        }), " (default): Generate query variations for better recall"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "false"
        }), ": Search only for your exact query"]
      }), "\n"]
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "customer churn analysis",
    "expand_query": true
  }'
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'from airweave import AirweaveSDK\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\nresults = await client.collections.search_advanced(\n    "your-collection-id",\n    {\n        "query": "customer churn analysis",\n        "expand_query": true\n    }\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });\n\nconst response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "payment failures",\n    expandQuery: true,\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Search Method"
    }), "\n", jsx(_components.p, {
      children: "The search method determines how Airweave searches your data. Different methods balance semantic understanding and keyword precision. You can use AI to understand meaning, traditional keyword matching, or both."
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "retrieval_strategy"
      })]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "hybrid"
        }), " (default): Best of both worlds - finds results by meaning AND exact keywords"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "neural"
        }), ": AI-powered search that understands what you mean, not just what you type"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "keyword"
        }), ": Traditional search that looks for exact word matches"]
      }), "\n"]
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "authentication flow security vulnerabilities",
    "retrieval_strategy": "hybrid"
  }'
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    "your-collection-id",\n    {\n        "query": "authentication flow security vulnerabilities",\n        "retrieval_strategy": "hybrid"\n    }\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "authentication flow security vulnerabilities",\n    retrievalStrategy: "hybrid",\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Filtering Results"
    }), "\n", jsx(_components.p, {
      children: "Applies structured filters before search, ensuring only relevant subsets are scanned. Useful for large datasets or when results must match specific attributes like source, date, or status."
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "filter"
      })]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Example 1: Filter by source"
      })
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
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
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    "your-collection-id",\n    {\n        "query": "deployment issues",\n        "filter": {\n            "must": [{\n                "key": "source_name",\n                "match": {"value": "GitHub"}  # Case-sensitive!\n            }]\n        }\n    }\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "deployment issues",\n    filter: {\n      must: [{\n        key: "source_name",\n        match: { value: "GitHub" }  // Case-sensitive!\n      }]\n    }\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Example 2: Multiple filters"
      })
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
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
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'from datetime import datetime, timezone, timedelta\n\nresults = await client.collections.search_advanced(\n    "your-collection-id",\n    {\n        "query": "customer feedback",\n        "filter": {\n            "must": [\n                {\n                    "key": "source_name",\n                    "match": {"any": ["Zendesk", "Intercom", "Slack"]}\n                },\n                {\n                    "key": "created_at",\n                    "range": {\n                        "gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()\n                    }\n                }\n            ]\n        }\n    }\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const oneWeekAgo = new Date();\noneWeekAgo.setDate(oneWeekAgo.getDate() - 7);\n\nconst response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "customer feedback",\n    filter: {\n      must: [\n        {\n          key: "source_name",\n          match: { any: ["Zendesk", "Intercom", "Slack"] }\n        },\n        {\n          key: "created_at",\n          range: {\n            gte: oneWeekAgo.toISOString()\n          }\n        }\n      ]\n    }\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Example 3: Exclude results"
      })
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
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
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    "your-collection-id",\n    {\n        "query": "bug reports",\n        "filter": {\n            "must_not": [{\n                "key": "status",\n                "match": {"any": ["resolved", "closed", "done"]}\n            }]\n        }\n    }\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "bug reports",\n    filter: {\n      must_not: [{\n        key: "status",\n        match: { any: ["resolved", "closed", "done"] }\n      }]\n    }\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Query Interpretation"
    }), "\n", jsx(Warning, {
      children: jsx(_components.p, {
        children: "This feature is currently in beta. It can occasionally filter too narrowly, so verify result counts."
      })
    }), "\n", jsx(_components.p, {
      children: "Query interpretation allows Airweave to automatically extract structured filters from a natural language query. Instead of manually defining metadata filters, you can simply describe what you are looking for, and Airweave will translate that description into filter conditions."
    }), "\n", jsxs(_components.p, {
      children: ["This feature is useful when you want to let end users search in plain English, for example ", jsx(_components.em, {
        children: '"open GitHub issues from last week"'
      }), " or ", jsx(_components.em, {
        children: '"critical bugs reported this month"'
      }), ". Airweave analyzes the query, identifies entities like dates, sources, or statuses, and applies them as filters."]
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "interpret_filters"
      }), " (boolean)"]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "false"
        }), " (default): You control all filters manually"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "true"
        }), ": AI extracts filters from your natural language query"]
      }), "\n"]
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "open asana tickets from last week",
    "interpret_filters": true
  }'
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="open asana tickets from last week",\n    interpret_filters=True\n)\n# AI understands: Asana source, open status, last 7 days\n\nresults = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="critical bugs from GitHub this month",\n    interpret_filters=True\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "open asana tickets from last week",\n    interpretFilters: true\n  }\n);\n\nconst response2 = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "critical bugs from GitHub this month",\n    interpretFilters: true\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Temporal Relevance"
    }), "\n", jsxs(Tip, {
      children: ["Learn more about this topic in our blogpost: ", jsx(_components.a, {
        href: "https://airweave.ai/blog/temporal-relevance-explained",
        children: "Deep Dive on Temporal Relevance "
      }), "."]
    }), "\n", jsx(_components.p, {
      children: "Temporal relevance adjusts the results ranking to prefer newer documents. This is valuable for time-sensitive data like messages, customer feedback, tickets, or news."
    }), "\n", jsx(_components.p, {
      children: "The scoring formula adjusts results based on age:"
    }), "\n", jsx(_components.p, {
      children: jsxs(_components.strong, {
        children: ["S", jsx("sub", {
          children: "final"
        }), " = S", jsx("sub", {
          children: "similarity"
        }), " × (1 − β + β × d(t))"]
      })
    }), "\n", jsx(_components.p, {
      children: "where,"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsxs(_components.strong, {
          children: ["S", jsx("sub", {
            children: "final"
          })]
        }), " = final relevance score"]
      }), "\n", jsxs(_components.li, {
        children: [jsxs(_components.strong, {
          children: ["S", jsx("sub", {
            children: "similarity"
          })]
        }), " = semantic similarity score"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "β"
        }), " = recency bias parameter (0 to 1)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "d(t)"
        }), " = time decay factor (0 = oldest, 1 = newest)."]
      }), "\n"]
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "temporal_relevance"
      }), " (0.0 to 1.0)"]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "0.3"
        }), " (default): Slightly prefer newer content"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "0.0"
        }), ": Don't care about dates, just find the best matches"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "1.0"
        }), ": Heavily prioritize the newest content"]
      }), "\n"]
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "project updates",
    "temporal_relevance": 0.7
  }'
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="project updates",\n    temporal_relevance=0.7\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "project updates",\n    temporalRelevance: 0.7,\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.p, {
      children: "Use this when freshness matters. For example, prioritizing the latest bug reports or recent customer complaints over historical ones."
    }), "\n", jsx(_components.h3, {
      children: "Pagination"
    }), "\n", jsx(_components.p, {
      children: "Control how many results you get and navigate through large result sets."
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameters"
      }), ":"]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "limit"
        }), ": How many results to return (1-1000, default: 20)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "offset"
        }), ": How many results to skip (for pagination, default: 0)"]
      }), "\n"]
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: "# Simple search with pagination\ncurl -X GET 'https://api.airweave.ai/collections/your-collection-id/search?query=data%20retention%20policies&limit=50&offset=50' \\\n  -H 'x-api-key: YOUR_API_KEY'\n"
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'response = await client.collections.search_collection(\n    readable_id="your-collection-id",\n    query="data retention policies",\n    limit=50,\n    offset=50,  # Skip first 50\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchCollection({\n  readableId: "your-collection-id",\n  query: "data retention policies",\n  limit: 50,\n  offset: 50,\n});\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "AI Reranking"
    }), "\n", jsx(_components.p, {
      children: "AI reranking takes the top set of results from the initial search and reorders them using a large language model. This improves accuracy in cases where keyword or semantic similarity alone might be misleading."
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "rerank"
      }), " (boolean)"]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "true"
        }), " (default): AI reviews and reorders results for best relevance"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "false"
        }), ": Skip reranking for faster results"]
      }), "\n"]
    }), "\n", jsx(Warning, {
      children: jsx(_components.p, {
        children: "Reranking adds about 10 seconds to your search. Turn it off if you need fast results."
      })
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "user authentication methods",
    "rerank": false
  }'
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="user authentication methods",\n    rerank=False\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "user authentication methods",\n    rerank: false,\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Generate AI Answers"
    }), "\n", jsx(_components.p, {
      children: "Airweave can return either raw results or a synthesized answer. When enabled, a large language model generates a natural language response based on the top results, including sources when available."
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Parameter"
      }), ": ", jsx(_components.code, {
        children: "generate_answer"
      }), " (boolean)"]
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "true"
        }), " (default): Generate an AI-synthesized answer from the top search results"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "false"
        }), ": Return only raw results"]
      }), "\n"]
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "What are our customer refund policies?",
    "generate_answer": true
  }'
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'results = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="What are our customer refund policies?",\n    generate_answer=True\n)\n# Access: results.completion\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'const response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "What are our customer refund policies?",\n    generateAnswer: true,\n  }\n);\n// Access: response.completion\n'
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Complete example"
    }), "\n", jsx(_components.p, {
      children: "Here's everything together in one search using the new API:"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
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
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'from airweave import AirweaveSDK\nfrom datetime import datetime, timezone, timedelta\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\nresults = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="customer feedback about pricing",\n    expand_query=True,\n    retrieval_strategy="hybrid",\n    filter={\n        "must": [{\n            "key": "source_name",\n            "match": {"any": ["Zendesk", "Slack"]}\n        }]\n    },\n    temporal_relevance=0.5,\n    rerank=True,\n    generate_answer=False,\n    limit=50,\n    offset=0\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });\n\nconst response = await client.collections.searchAdvanced(\n  "your-collection-id",\n  {\n    query: "customer feedback about pricing",\n    expandQuery: true,\n    retrievalStrategy: "hybrid",\n    filter: {\n      must: [{\n        key: "source_name",\n        match: { any: ["Zendesk", "Slack"] }\n      }]\n    },\n    temporalRelevance: 0.5,\n    rerank: true,\n    generateAnswer: false,\n    limit: 50,\n    offset: 0\n  }\n);\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Legacy API Example"
    }), "\n", jsx(_components.p, {
      children: "If you're still using the legacy API, here's how the same query looks (deprecated):"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://api.airweave.ai/collections/your-collection-id/search' \\
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
`
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: '# Using old parameter names (still works but deprecated)\nresults = await client.collections.search_advanced(\n    readable_id="your-collection-id",\n    query="customer feedback about pricing",\n    expansion_strategy="auto",  # ❌ Use expand_query instead\n    search_method="hybrid",     # ❌ Use retrieval_strategy instead\n    recency_bias=0.5,           # ❌ Use temporal_relevance instead\n    enable_reranking=True,      # ❌ Use rerank instead\n    response_type="raw",        # ❌ Use generate_answer instead\n)\n'
        })
      })]
    }), "\n", jsx(Card, {
      title: "Ready to search?",
      icon: "rocket",
      children: jsxs(_components.p, {
        children: ["Try these examples live in our ", jsx(_components.a, {
          href: "https://docs.airweave.ai/api-reference/collections/search-collections-readable-id-search-post",
          children: "interactive API documentation"
        }), ". You can execute real searches and see responses instantly!"]
      })
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
