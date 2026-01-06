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
  };
  return jsxs(Fragment, {
    children: [jsxs(_components.p, {
      children: ["The ", jsx(_components.code, {
        children: "@airweave/vercel-ai-sdk"
      }), " package provides an ", jsx(_components.code, {
        children: "airweaveSearch"
      }), " tool that integrates seamlessly with the ", jsx(_components.a, {
        href: "https://ai-sdk.dev",
        children: "Vercel AI SDK"
      }), "."]
    }), "\n", jsx(_components.h3, {
      children: "Prerequisites"
    }), "\n", jsx(_components.p, {
      children: "Before you start you'll need:"
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
      children: "Installation"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-bash",
        children: "npm install ai @ai-sdk/openai @airweave/vercel-ai-sdk\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "Quick Start"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-typescript",
        children: "import { generateText } from 'ai';\nimport { openai } from '@ai-sdk/openai';\nimport { airweaveSearch } from '@airweave/vercel-ai-sdk';\n\nconst { text } = await generateText({\n  model: openai('gpt-4o'),\n  prompt: 'What were the key decisions from last week?',\n  tools: {\n    search: airweaveSearch({\n      defaultCollection: 'my-knowledge-base',\n    }),\n  },\n  maxSteps: 3,\n});\n\nconsole.log(text);\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "Configuration"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-typescript",
        children: "airweaveSearch({\n  // API key (defaults to AIRWEAVE_API_KEY env var)\n  apiKey: 'your-api-key',\n\n  // Default collection to search\n  defaultCollection: 'my-collection',\n\n  // Max results per search (default: 10)\n  defaultLimit: 20,\n\n  // Generate AI answer from results (default: false)\n  generateAnswer: true,\n\n  // Query expansion for better recall (default: true)\n  expandQuery: true,\n\n  // Rerank for relevance (default: true)\n  rerank: true,\n\n  // Base URL for self-hosted instances\n  baseUrl: 'https://your-instance.airweave.ai',\n});\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Option"
          }), jsx(_components.th, {
            children: "Type"
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
              children: "apiKey"
            })
          }), jsx(_components.td, {
            children: "string"
          }), jsxs(_components.td, {
            children: [jsx(_components.code, {
              children: "AIRWEAVE_API_KEY"
            }), " env"]
          }), jsx(_components.td, {
            children: "Your Airweave API key"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "baseUrl"
            })
          }), jsx(_components.td, {
            children: "string"
          }), jsx(_components.td, {
            children: "-"
          }), jsx(_components.td, {
            children: "Base URL for self-hosted instances"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "defaultCollection"
            })
          }), jsx(_components.td, {
            children: "string"
          }), jsx(_components.td, {
            children: "-"
          }), jsx(_components.td, {
            children: "Default collection readable ID to search"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "defaultLimit"
            })
          }), jsx(_components.td, {
            children: "number"
          }), jsx(_components.td, {
            children: "10"
          }), jsx(_components.td, {
            children: "Default maximum number of results"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "generateAnswer"
            })
          }), jsx(_components.td, {
            children: "boolean"
          }), jsx(_components.td, {
            children: "false"
          }), jsx(_components.td, {
            children: "Generate an AI-powered answer from results"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "expandQuery"
            })
          }), jsx(_components.td, {
            children: "boolean"
          }), jsx(_components.td, {
            children: "true"
          }), jsx(_components.td, {
            children: "Expand query with variations for better recall"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "rerank"
            })
          }), jsx(_components.td, {
            children: "boolean"
          }), jsx(_components.td, {
            children: "true"
          }), jsx(_components.td, {
            children: "Rerank results for improved relevance"
          })]
        })]
      })]
    }), "\n", jsx(_components.h3, {
      children: "Environment Variables"
    }), "\n", jsx(_components.p, {
      children: "Set your API key as an environment variable. You can copy your API key from the Airweave dashboard."
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-bash",
        children: "AIRWEAVE_API_KEY=your-api-key\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "TypeScript Support"
    }), "\n", jsx(_components.p, {
      children: "Full TypeScript types are included:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-typescript",
        children: "import {\n  airweaveSearch,\n  AirweaveSearchOptions,\n  AirweaveSearchResult,\n  AirweaveSearchResultItem\n} from '@airweave/vercel-ai-sdk';\n\nconst config: AirweaveSearchOptions = {\n  defaultCollection: 'my-collection',\n  defaultLimit: 10,\n};\n\nconst search = airweaveSearch(config);\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "Result Types"
    }), "\n", jsx(_components.p, {
      children: "Each search result includes:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-typescript",
        children: 'interface AirweaveSearchResultItem {\n  id: string;                    // Entity ID\n  score: number;                 // Relevance score\n  payload: {\n    entity_id?: string;\n    name?: string;\n    created_at?: string;\n    textual_representation?: string;\n    breadcrumbs?: AirweaveBreadcrumb[];\n    airweave_system_metadata?: {\n      source_name?: string;      // e.g., "notion", "slack"\n      entity_type?: string;      // e.g., "NotionPageEntity"\n      sync_id?: string;\n      chunk_index?: number;\n    };\n    // Plus source-specific fields\n  };\n}\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Learn More"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://ai-sdk.dev/docs/introduction",
          children: "Vercel AI SDK Documentation"
        })
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://ai-sdk.dev/tools-registry/airweave",
          children: "Airweave on Vercel Tool Registry"
        })
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://github.com/airweave-ai/airweave",
          children: "Airweave GitHub"
        })
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
export {
  MDXContent as default
};
