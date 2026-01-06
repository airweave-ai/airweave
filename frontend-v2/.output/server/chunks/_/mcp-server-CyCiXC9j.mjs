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
    blockquote: "blockquote",
    code: "code",
    h3: "h3",
    li: "li",
    ol: "ol",
    p: "p",
    pre: "pre",
    strong: "strong",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Tab, Tabs } = _components;
  if (!Tab) _missingMdxReference("Tab");
  if (!Tabs) _missingMdxReference("Tabs");
  return jsxs(Fragment, {
    children: [jsx(_components.h3, {
      children: "Prerequisites"
    }), "\n", jsx(_components.p, {
      children: "Before you start you’ll need:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "A collection with data"
        }), ": at least one source connection must have completed its initial sync. See the ", jsx(_components.a, {
          href: "https://docs.airweave.ai/quickstart",
          children: "Quickstart"
        }), " if you need to set this up."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "An API key"
        }), ": Create one in the Airweave dashboard under ", jsx(_components.strong, {
          children: "API Keys"
        }), "."]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Set-up"
    }), "\n", jsxs(Tabs, {
      children: [jsxs(Tab, {
        title: "Cursor",
        children: [jsxs(_components.blockquote, {
          children: ["\n", jsxs(_components.p, {
            children: [jsx(_components.strong, {
              children: "Requirement"
            }), ": Cursor version 0.45.6 or later"]
          }), "\n"]
        }), jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: ["Open ", jsx(_components.strong, {
              children: "Cursor Settings"
            })]
          }), "\n", jsxs(_components.li, {
            children: ["Go to ", jsx(_components.strong, {
              children: "Features > MCP Servers"
            })]
          }), "\n", jsxs(_components.li, {
            children: ["Click ", jsx(_components.strong, {
              children: '"+ Add new global MCP server"'
            })]
          }), "\n", jsx(_components.li, {
            children: "Add this configuration:"
          }), "\n"]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-json",
            children: '{\n  "mcpServers": {\n    "airweave-search": {\n      "command": "npx",\n      "args": ["-y", "airweave-mcp-search"],\n      "env": {\n        "AIRWEAVE_API_KEY": "your-api-key",\n        "AIRWEAVE_COLLECTION": "your-collection-id"\n      }\n    }\n  }\n}\n'
          })
        })]
      }), jsxs(Tab, {
        title: "Claude Desktop",
        children: [jsx(_components.p, {
          children: "Add the following to your Claude Desktop config file and restart Claude Desktop afterwards.\nAfter a restart the search tool will appear in Claude’s composer."
        }), jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "macOS/Linux"
            }), ": ", jsx(_components.code, {
              children: "~/.claude/claude_desktop_config.json"
            })]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Windows"
            }), ": ", jsx(_components.code, {
              children: "%APPDATA%\\claude\\claude_desktop_config.json"
            })]
          }), "\n"]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-json",
            children: '{\n  "mcpServers": {\n    "airweave-search": {\n      "command": "npx",\n      "args": ["-y", "airweave-mcp-search"],\n      "env": {\n        "AIRWEAVE_API_KEY": "your-api-key",\n        "AIRWEAVE_COLLECTION": "your-collection-id"\n      }\n    }\n  }\n}\n'
          })
        })]
      }), jsxs(Tab, {
        title: "VS Code",
        children: [jsxs(_components.p, {
          children: ["Add to your User Settings (JSON) via ", jsx(_components.strong, {
            children: "Ctrl+Shift+P"
          }), " → ", jsx(_components.strong, {
            children: '"Preferences: Open User Settings (JSON)"'
          }), ":"]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-json",
            children: '{\n  "mcp": {\n    "inputs": [\n      {\n        "type": "promptString",\n        "id": "airweaveApiKey",\n        "description": "Airweave API Key",\n        "password": true\n      },\n      {\n        "type": "promptString",\n        "id": "airweaveCollection",\n        "description": "Airweave Collection ID"\n      }\n    ],\n    "servers": {\n      "airweave": {\n        "command": "npx",\n        "args": ["-y", "airweave-mcp-search"],\n        "env": {\n          "AIRWEAVE_API_KEY": "${input:airweaveApiKey}",\n          "AIRWEAVE_COLLECTION": "${input:airweaveCollection}"\n        }\n      }\n    }\n  }\n}\n'
          })
        })]
      })]
    }), "\n", jsx(_components.p, {
      children: "These environment variables can be set:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "AIRWEAVE_API_KEY"
        }), " (Required): Authenticates the MCP server with the Airweave API so it can run searches on your behalf."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "AIRWEAVE_COLLECTION"
        }), " (Required): Readable ID of the collection to query. All ", jsx(_components.code, {
          children: "search"
        }), " calls are scoped to this collection."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "AIRWEAVE_BASE_URL"
        }), " (Optional): Override if you're running a self-hosted Airweave instance (default: ", jsx(_components.code, {
          children: "https://api.airweave.ai"
        }), ")."]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Available tools"
    }), "\n", jsx(_components.p, {
      children: "The MCP server provides two tools:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "search"
        }), ": Enhanced search across all source connections in the collection with full parameter control and optional AI completion."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "get-config"
        }), ": View current configuration and connection status so you can verify everything is working correctly. No parameters required."]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Advanced Search Features"
    }), "\n", jsxs(_components.p, {
      children: ["The search tool uses the ", jsx(_components.strong, {
        children: "POST"
      }), " endpoint for full control over search parameters."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Available Parameters:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "retrieval_strategy"
        }), ": Choose between 'hybrid', 'neural', or 'keyword' search (default: 'hybrid')"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "expand_query"
        }), ": Generate query variations for better recall (default: true)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "interpret_filters"
        }), ": Extract filters from natural language (default: false)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "rerank"
        }), ": LLM-based result reranking for improved relevance (default: true)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "generate_answer"
        }), ": AI-generated completion from results (default: true)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "temporal_relevance"
        }), ": Recency weighting from 0.0 to 1.0 (default: 0.3)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "limit"
        }), ": Maximum number of results (default: 1000)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "offset"
        }), ": Pagination offset (default: 0)"]
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Natural Language Examples:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: ['"Use neural search for semantic similarity" → ', jsx(_components.code, {
          children: 'retrieval_strategy: "neural"'
        })]
      }), "\n", jsxs(_components.li, {
        children: ['"Search without expanding the query" → ', jsx(_components.code, {
          children: "expand_query: false"
        })]
      }), "\n", jsxs(_components.li, {
        children: ['"Extract filters from my query" → ', jsx(_components.code, {
          children: "interpret_filters: true"
        })]
      }), "\n", jsxs(_components.li, {
        children: ['"Disable reranking for faster results" → ', jsx(_components.code, {
          children: "rerank: false"
        })]
      }), "\n", jsxs(_components.li, {
        children: ['"Just return results, no AI summary" → ', jsx(_components.code, {
          children: "generate_answer: false"
        })]
      }), "\n", jsxs(_components.li, {
        children: ['"Prioritize recent documents" → ', jsx(_components.code, {
          children: "temporal_relevance: 0.8"
        })]
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
