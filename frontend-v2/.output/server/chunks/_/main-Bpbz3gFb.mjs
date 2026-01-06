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
    h2: "h2",
    h3: "h3",
    li: "li",
    p: "p",
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
  }, { Accordion, Card } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
  if (!Card) _missingMdxReference("Card");
  return jsxs(Fragment, {
    children: ["\n", jsxs("div", {
      className: "connector-header",
      style: {
        display: "flex",
        alignItems: "center",
        gap: "12px",
        marginBottom: "24px"
      },
      children: [jsx("img", {
        src: "icon.svg",
        alt: "Notion logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Notion"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Notion source connector integrates with the Notion API to extract and synchronize content."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Notion workspace."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to databases, pages, and content with advanced content\naggregation, lazy loading, and file processing capabilities for optimal performance."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/notion.py",
      children: jsx(_components.p, {
        children: "Explore the Notion connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses ", jsx(_components.strong, {
        children: "OAuth 2.0 authentication"
      }), ". You can connect through the Airweave UI or API using the OAuth flow."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Supported authentication methods:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "OAuth Browser Flow (recommended for UI)"
      }), "\n", jsx(_components.li, {
        children: "OAuth Token (for programmatic access)"
      }), "\n", jsx(_components.li, {
        children: "Auth Provider (enterprise SSO)"
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "This connector does not have any additional configuration options."
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "NotionDatabaseEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Notion database."
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
              children: "title"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The title of the database"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The description of the database"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Database properties schema"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties_text"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Human-readable schema description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The ID of the parent"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The type of the parent (workspace, page_id, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The icon of the database"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "cover"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The cover of the database"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the database is archived"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_inline"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the database is inline"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The URL of the database"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "NotionPageEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Notion page with aggregated content."
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
              children: "parent_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The ID of the parent"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The type of the parent (workspace, page_id, database_id, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The title of the page"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full aggregated content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Formatted page properties for search"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties_text"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Human-readable properties text"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "property_entities"
            }), jsx(_components.td, {
              children: "List[Any]"
            }), jsx(_components.td, {
              children: "Structured property entities"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "files"
            }), jsx(_components.td, {
              children: "List[Any]"
            }), jsx(_components.td, {
              children: "Files referenced in the page"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The icon of the page"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "cover"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The cover of the page"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the page is archived"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "in_trash"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the page is in trash"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The URL of the page"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_blocks_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of blocks processed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "max_depth"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Maximum nesting depth of blocks"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "NotionPropertyEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Notion database page property."
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
              children: "property_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The ID of the property"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "property_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The name of the property"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "property_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The type of the property"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "page_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The ID of the page this property belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "database_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The ID of the database this property belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "value"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "The raw value of the property"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "formatted_value"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The formatted/display value of the property"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "NotionFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Notion file."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.notion.com/reference/file-object",
          children: "https://developers.notion.com/reference/file-object"
        })]
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
              children: "file_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the file in Notion"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "expiry_time"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "When the file URL expires (for Notion-hosted files)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "caption"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The caption of the file"
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
