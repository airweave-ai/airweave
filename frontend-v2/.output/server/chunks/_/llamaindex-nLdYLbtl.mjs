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
    h4: "h4",
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
        children: "llama-index-tools-airweave"
      }), " package provides an ", jsx(_components.code, {
        children: "AirweaveToolSpec"
      }), " that gives your LlamaIndex agents access to Airweave's semantic search capabilities."]
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
        children: "pip install llama-index llama-index-tools-airweave\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "Quick Start"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: `import os
import asyncio
from llama_index.tools.airweave import AirweaveToolSpec
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

# Initialize the Airweave tool
airweave_tool = AirweaveToolSpec(
    api_key=os.environ["AIRWEAVE_API_KEY"],
)

# Create an agent with the Airweave tools
agent = FunctionAgent(
    tools=airweave_tool.to_tool_list(),
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="""You are a helpful assistant that can search through
    Airweave collections to answer questions about your organization's data.""",
)

# Use the agent to search your data
async def main():
    response = await agent.run(
        "Search the finance-data collection for Q4 revenue reports"
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
`
      })
    }), "\n", jsx(_components.h3, {
      children: "Available Tools"
    }), "\n", jsxs(_components.p, {
      children: ["The ", jsx(_components.code, {
        children: "AirweaveToolSpec"
      }), " provides five tools that your agent can use:"]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "search_collection"
      })
    }), "\n", jsx(_components.p, {
      children: "Simple search in a collection with default settings (most common use case)."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Type"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "collection_id"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "The readable ID of the collection"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "query"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "Your search query"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "limit"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Max results to return (default: 10)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "offset"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Pagination offset (default: 0)"
          })]
        })]
      })]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "advanced_search_collection"
      })
    }), "\n", jsx(_components.p, {
      children: "Advanced search with full control over retrieval parameters."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Type"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "collection_id"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "The readable ID of the collection"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "query"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "Your search query"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "limit"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Max results to return (default: 10)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "offset"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Pagination offset (default: 0)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "retrieval_strategy"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsxs(_components.td, {
            children: [jsx(_components.code, {
              children: '"hybrid"'
            }), ", ", jsx(_components.code, {
              children: '"neural"'
            }), ", or ", jsx(_components.code, {
              children: '"keyword"'
            })]
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "temporal_relevance"
            })
          }), jsx(_components.td, {
            children: "float"
          }), jsx(_components.td, {
            children: "Weight recent content (0.0-1.0)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "expand_query"
            })
          }), jsx(_components.td, {
            children: "bool"
          }), jsx(_components.td, {
            children: "Generate query variations"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "interpret_filters"
            })
          }), jsx(_components.td, {
            children: "bool"
          }), jsx(_components.td, {
            children: "Extract filters from natural language"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "rerank"
            })
          }), jsx(_components.td, {
            children: "bool"
          }), jsx(_components.td, {
            children: "Use LLM-based reranking"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "generate_answer"
            })
          }), jsx(_components.td, {
            children: "bool"
          }), jsx(_components.td, {
            children: "Generate natural language answer"
          })]
        })]
      })]
    }), "\n", jsxs(_components.p, {
      children: ["Returns a dictionary with ", jsx(_components.code, {
        children: "documents"
      }), " list and optional ", jsx(_components.code, {
        children: "answer"
      }), " field."]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "search_and_generate_answer"
      })
    }), "\n", jsx(_components.p, {
      children: "Convenience method that searches and returns a direct natural language answer (RAG-style)."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Type"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "collection_id"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "The readable ID of the collection"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "query"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "Your question in natural language"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "limit"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Max results to consider (default: 10)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "use_reranking"
            })
          }), jsx(_components.td, {
            children: "bool"
          }), jsx(_components.td, {
            children: "Use reranking (default: True)"
          })]
        })]
      })]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "list_collections"
      })
    }), "\n", jsx(_components.p, {
      children: "List all collections in your organization."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Type"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "skip"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Pagination skip (default: 0)"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "limit"
            })
          }), jsx(_components.td, {
            children: "int"
          }), jsx(_components.td, {
            children: "Max collections to return (default: 100)"
          })]
        })]
      })]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "get_collection_info"
      })
    }), "\n", jsx(_components.p, {
      children: "Get detailed information about a specific collection."
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Parameter"
          }), jsx(_components.th, {
            children: "Type"
          }), jsx(_components.th, {
            children: "Description"
          })]
        })
      }), jsx(_components.tbody, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "collection_id"
            })
          }), jsx(_components.td, {
            children: "str"
          }), jsx(_components.td, {
            children: "The readable ID of the collection"
          })]
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Advanced Examples"
    }), "\n", jsx(_components.h4, {
      children: "Direct Tool Usage"
    }), "\n", jsx(_components.p, {
      children: "You can use the tools directly without an agent:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: `from llama_index.tools.airweave import AirweaveToolSpec

airweave_tool = AirweaveToolSpec(api_key="your-key")

# List collections
collections = airweave_tool.list_collections()
print(f"Found {len(collections)} collections")

# Simple search
results = airweave_tool.search_collection(
    collection_id="finance-data",
    query="Q4 revenue reports",
    limit=5
)

for doc in results:
    print(f"Score: {doc.metadata.get('score', 'N/A')}")
    print(f"Text: {doc.text[:200]}...")
`
      })
    }), "\n", jsx(_components.h4, {
      children: "Advanced Search with All Options"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: `result = airweave_tool.advanced_search_collection(
    collection_id="finance-data",
    query="Q4 revenue reports",
    limit=20,
    retrieval_strategy="hybrid",
    temporal_relevance=0.3,
    expand_query=True,
    interpret_filters=True,
    rerank=True,
    generate_answer=True,
)

documents = result["documents"]
if "answer" in result:
    print(f"Generated Answer: {result['answer']}")
`
      })
    }), "\n", jsx(_components.h4, {
      children: "RAG-Style Direct Answers"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'answer = airweave_tool.search_and_generate_answer(\n    collection_id="finance-data",\n    query="What was our Q4 revenue growth?",\n    limit=10,\n    use_reranking=True,\n)\nprint(answer)  # "Q4 revenue grew by 23% to $45M compared to Q3..."\n'
      })
    }), "\n", jsx(_components.h4, {
      children: "Using Different Retrieval Strategies"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: '# Keyword search for exact term matching\nresults = airweave_tool.advanced_search_collection(\n    collection_id="legal-docs",\n    query="GDPR compliance",\n    retrieval_strategy="keyword",\n)\n\n# Neural search for semantic understanding\nresults = airweave_tool.advanced_search_collection(\n    collection_id="research-papers",\n    query="papers about transformer architectures",\n    retrieval_strategy="neural",\n)\n\n# Hybrid search (default) - best of both worlds\nresults = airweave_tool.advanced_search_collection(\n    collection_id="all-docs",\n    query="machine learning best practices",\n    retrieval_strategy="hybrid",\n)\n'
      })
    }), "\n", jsx(_components.h4, {
      children: "Temporal Relevance"
    }), "\n", jsx(_components.p, {
      children: "Weight recent documents higher in results:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'results = airweave_tool.advanced_search_collection(\n    collection_id="news-articles",\n    query="AI breakthroughs",\n    temporal_relevance=0.8,  # 0.0 = no recency bias, 1.0 = only recent matters\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Custom Base URL"
    }), "\n", jsx(_components.p, {
      children: "If you're self-hosting Airweave:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'airweave_tool = AirweaveToolSpec(\n    api_key="your-api-key",\n    base_url="https://your-airweave-instance.com",\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Using with Local Models"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-bash",
        children: "pip install llama-index-llms-ollama\n"
      })
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-python",
        children: 'from llama_index.llms.ollama import Ollama\n\nagent = FunctionAgent(\n    tools=airweave_tool.to_tool_list(),\n    llm=Ollama(model="llama3.1", request_timeout=360.0),\n)\n'
      })
    }), "\n", jsx(_components.h3, {
      children: "Learn More"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://docs.llamaindex.ai/",
          children: "LlamaIndex Documentation"
        })
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://llamahub.ai/l/tools/llama-index-tools-airweave?from=all",
          children: "LlamaIndex Airweave Tool on LlamaHub"
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
