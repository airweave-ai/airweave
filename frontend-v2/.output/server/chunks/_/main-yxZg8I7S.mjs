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
    code: "code",
    h2: "h2",
    h3: "h3",
    p: "p",
    table: "table",
    tbody: "tbody",
    td: "td",
    th: "th",
    thead: "thead",
    tr: "tr",
    ...useMDXComponents(),
    ...props.components
  }, { Accordion, Card, ParamField } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
  if (!Card) _missingMdxReference("Card");
  if (!ParamField) _missingMdxReference("ParamField");
  return jsxs(Fragment, {
    children: ["\n", jsxs("div", {
      className: "connector-header",
      children: [jsx("img", {
        src: "icon.svg",
        alt: "Elasticsearch logo",
        width: "72",
        height: "72",
        className: "connector-icon"
      }), jsxs("div", {
        className: "connector-info",
        children: [jsx("h1", {
          children: "Elasticsearch"
        }), jsx("p", {
          children: "Connect your Elasticsearch data to Airweave"
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Overview"
    }), "\n", jsx(_components.p, {
      children: "The Elasticsearch connector allows you to sync data from Elasticsearch into Airweave, making it available for search and retrieval by your agents."
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.h3, {
      children: "ElasticsearchSource"
    }), "\n", jsx(_components.p, {
      children: "Elasticsearch source implementation."
    }), "\n", jsx(_components.p, {
      children: "Connects to an Elasticsearch cluster, retrieves index metadata and documents\nfor configured indices using the scroll API."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/elasticsearch.py",
      children: jsx(_components.p, {
        children: "Explore the Elasticsearch connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses a custom authentication configuration class: ", jsx(_components.code, {
        children: "ElasticsearchAuthConfig"
      }), "."]
    }), "\n", jsxs(Card, {
      title: "Authentication Configuration",
      className: "auth-config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "Elasticsearch authentication credentials schema."
      }), jsx(ParamField, {
        path: "host",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The full URL to the Elasticsearch server, including http or https"
        })
      }), jsx(ParamField, {
        path: "port",
        type: "int",
        required: true,
        children: jsx(_components.p, {
          children: "The port of the elasticsearch database"
        })
      }), jsx(ParamField, {
        path: "indices",
        type: "str",
        required: false,
        default: "*",
        children: jsx(_components.p, {
          children: "Comma separated list of indices to sync. Use '*' for all indices."
        })
      }), jsx(ParamField, {
        path: "fields",
        type: "str",
        required: false,
        default: "*",
        children: jsx(_components.p, {
          children: "List of fields to sync from each document. For all fields, use '*'"
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Entities"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "ElasticsearchIndexEntity",
      children: [jsx(_components.p, {
        children: "Schema for Elasticsearch index entities."
      }), jsxs(_components.table, {
        children: [jsx(_components.thead, {
          children: jsxs(_components.tr, {
            children: [jsx(_components.th, {
              children: "Field"
            }), jsx(_components.th, {
              children: "Type"
            }), jsx(_components.th, {
              children: "Description"
            })]
          })
        }), jsxs(_components.tbody, {
          children: [jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "index"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the Elasticsearch index"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "health"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Health status of the index"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the index"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "docs_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of documents in the index"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "docs_deleted"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of deleted documents in index"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "store_size"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Store size of the index"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ElasticsearchDocumentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Elasticsearch document entities."
      }), jsxs(_components.table, {
        children: [jsx(_components.thead, {
          children: jsxs(_components.tr, {
            children: [jsx(_components.th, {
              children: "Field"
            }), jsx(_components.th, {
              children: "Type"
            }), jsx(_components.th, {
              children: "Description"
            })]
          })
        }), jsxs(_components.tbody, {
          children: [jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "index"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the index this document belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "doc_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Document ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "source"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Source document content"
            })]
          })]
        })]
      })]
    }), "\n"]
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
