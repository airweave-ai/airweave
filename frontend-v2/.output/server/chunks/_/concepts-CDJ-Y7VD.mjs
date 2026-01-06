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
    table: "table",
    tbody: "tbody",
    td: "td",
    th: "th",
    thead: "thead",
    tr: "tr",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { CodeGroup, Warning } = _components;
  if (!CodeGroup) _missingMdxReference("CodeGroup");
  if (!Warning) _missingMdxReference("Warning");
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "Airweave's search functionality enables you to query across all your connected data sources simultaneously. This unified search approach means you can find information whether it lives in GitHub, Slack, Asana, or any other integrated system—all through a single API call."
    }), "\n", jsx(_components.h2, {
      children: "Core Concepts"
    }), "\n", jsx(_components.h3, {
      children: "Query"
    }), "\n", jsx(_components.p, {
      children: "The query is your search text—the question or keywords you're looking for across your data. Airweave uses semantic search, which means it understands the meaning behind your query, not just exact keyword matches."
    }), "\n", jsxs(CodeGroup, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-text",
          children: '"What are our customer refund policies?"\n"Show me recent security incidents"\n"Find all discussions about Q4 planning"\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-text",
          children: '"payment gateway integration"\n"user authentication flow"\n"performance optimization"\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-text",
          children: '"customer complaints about shipping delays in the last month"\n"technical debt in the authentication module"\n"feature requests related to mobile app"\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Response Types"
    }), "\n", jsx(_components.p, {
      children: "Airweave provides two response formats, each suited to different use cases:"
    }), "\n", jsxs(_components.p, {
      children: [jsxs(_components.strong, {
        children: ["Raw Response (", jsx(_components.code, {
          children: "raw"
        }), ")"]
      }), ": Returns the actual search results as structured data. Use this when you need to process results programmatically or display them in your own interface."]
    }), "\n", jsxs(_components.p, {
      children: [jsxs(_components.strong, {
        children: ["Completion Response (", jsx(_components.code, {
          children: "completion"
        }), ")"]
      }), ": Returns an AI-generated natural language answer based on the search results. The AI synthesizes information from multiple sources into a coherent response. Use this for conversational interfaces or when you need summarized insights."]
    }), "\n", jsx(_components.h3, {
      children: "Query Expansion"
    }), "\n", jsx(_components.p, {
      children: "Query expansion improves search recall by automatically generating related search terms. This helps find relevant content that might use different terminology than your original query."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Strategy"
          }), jsx(_components.th, {
            children: "Description"
          }), jsx(_components.th, {
            children: "Use Case"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "auto"
            })
          }), jsx(_components.td, {
            children: "Let Airweave decide whether to expand based on query complexity"
          }), jsx(_components.td, {
            children: "Default choice for most searches"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "llm"
            })
          }), jsx(_components.td, {
            children: "Uses language models to generate synonyms and related terms"
          }), jsx(_components.td, {
            children: "Maximum recall for broad topics"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "no_expansion"
            })
          }), jsx(_components.td, {
            children: "Searches only for the exact query"
          }), jsx(_components.td, {
            children: "Precise searches or proper nouns"
          })]
        })]
      })]
    }), "\n", jsx(_components.h3, {
      children: "Pagination"
    }), "\n", jsx(_components.p, {
      children: "For searches returning many results, pagination controls help manage the response size:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.code, {
            children: "limit"
          })
        }), ": Number of results per page (1-1000, default: 20)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.code, {
            children: "offset"
          })
        }), ": Number of results to skip (default: 0)"]
      }), "\n"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Get the second page of 50 results\nsearch_request = SearchRequest(\n    query="project updates",\n    limit=50,\n    offset=50  # Skip first 50 results\n)\n'
      })
    }), "\n", jsx(Warning, {
      children: jsxs(_components.p, {
        children: ["When using query expansion (", jsx(_components.code, {
          children: "auto"
        }), " or ", jsx(_components.code, {
          children: "llm"
        }), "), pagination may return inconsistent results across requests. For reliable pagination, set ", jsx(_components.code, {
          children: 'expansion_strategy="no_expansion"'
        }), "."]
      })
    }), "\n", jsx(_components.h3, {
      children: "Score Threshold"
    }), "\n", jsx(_components.p, {
      children: "The score threshold filters results by relevance score (0.0-1.0). Higher scores indicate better semantic matches. Setting a threshold helps eliminate marginally relevant results."
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Only return highly relevant results\nsearch_request = SearchRequest(\n    query="security vulnerabilities",\n    score_threshold=0.7  # Only results with 70%+ relevance\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Summarization"
    }), "\n", jsx(_components.p, {
      children: "When enabled, the summarization feature provides a concise overview of the search results. This is particularly useful when dealing with large result sets or when you need a quick understanding of the findings."
    }), "\n", jsx(_components.h2, {
      children: "Quick Reference"
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Type"
          }), jsx(_components.th, {
            children: "Default"
          }), jsx(_components.th, {
            children: "Valid Range"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "query"
            })
          }), jsx(_components.td, {
            children: "string"
          }), jsx(_components.td, {
            children: "required"
          }), jsx(_components.td, {
            children: "1-1000 chars"
          }), jsx(_components.td, {
            children: "Search text"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "response_type"
            })
          }), jsx(_components.td, {
            children: "enum"
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "raw"
            })
          }), jsxs(_components.td, {
            children: [jsx(_components.code, {
              children: "raw"
            }), ", ", jsx(_components.code, {
              children: "completion"
            })]
          }), jsx(_components.td, {
            children: "Response format"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "expansion_strategy"
            })
          }), jsx(_components.td, {
            children: "enum"
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "auto"
            })
          }), jsxs(_components.td, {
            children: [jsx(_components.code, {
              children: "auto"
            }), ", ", jsx(_components.code, {
              children: "llm"
            }), ", ", jsx(_components.code, {
              children: "no_expansion"
            })]
          }), jsx(_components.td, {
            children: "Query expansion method"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "limit"
            })
          }), jsx(_components.td, {
            children: "integer"
          }), jsx(_components.td, {
            children: "20"
          }), jsx(_components.td, {
            children: "1-1000"
          }), jsx(_components.td, {
            children: "Results per page"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "offset"
            })
          }), jsx(_components.td, {
            children: "integer"
          }), jsx(_components.td, {
            children: "0"
          }), jsx(_components.td, {
            children: "≥ 0"
          }), jsx(_components.td, {
            children: "Results to skip"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "score_threshold"
            })
          }), jsx(_components.td, {
            children: "float"
          }), jsx(_components.td, {
            children: "none"
          }), jsx(_components.td, {
            children: "0.0-1.0"
          }), jsx(_components.td, {
            children: "Minimum relevance score"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "summarize"
            })
          }), jsx(_components.td, {
            children: "boolean"
          }), jsx(_components.td, {
            children: "false"
          }), jsx(_components.td, {
            children: "-"
          }), jsx(_components.td, {
            children: "Enable result summarization"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "filter"
            })
          }), jsx(_components.td, {
            children: "object"
          }), jsx(_components.td, {
            children: "none"
          }), jsx(_components.td, {
            children: "-"
          }), jsx(_components.td, {
            children: "Qdrant filter object"
          })]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Next Steps"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: ["Learn about ", jsx(_components.a, {
          href: "/search/filters",
          children: "filtering search results"
        }), " to narrow down results by metadata"]
      }), "\n", jsxs(_components.li, {
        children: ["Explore ", jsx(_components.a, {
          href: "/search/examples",
          children: "practical examples"
        }), " of search queries"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: jsx(_components.a, {
            href: "/api-reference/collections/search-collection-collections-readable-id-search-get",
            children: "API Reference"
          })
        }), " - Complete API details"]
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
