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
      style: {
        display: "flex",
        alignItems: "center",
        gap: "12px",
        marginBottom: "24px"
      },
      children: [jsx("img", {
        src: "icon.svg",
        alt: "Attio logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Attio"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Attio source connector integrates with the Attio API to extract CRM data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes your Attio workspace including objects, lists, records, and notes."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/attio.py",
      children: jsx(_components.p, {
        children: "Explore the Attio connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsx(_components.p, {
      children: "This connector uses a custom authentication configuration."
    }), "\n", jsxs(Card, {
      title: "Authentication Configuration",
      className: "auth-config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "Attio authentication credentials schema."
      }), jsx(ParamField, {
        path: "api_key",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The API key for Attio. Generate one in Workspace Settings > Developers."
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "This connector does not have any additional configuration options."
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "AttioObjectEntity",
      children: [jsx(_components.p, {
        children: "Schema for Attio Object (e.g., Companies, People, Deals)."
      }), jsx(_components.p, {
        children: "Objects are the core data types in Attio's CRM."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.attio.com/rest-api/endpoint-reference/objects",
          children: "https://docs.attio.com/rest-api/endpoint-reference/objects"
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
              children: "singular_noun"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Singular name of the object (e.g., 'Company')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "plural_noun"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Plural name of the object (e.g., 'Companies')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "api_slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "API slug for the object"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Icon representing this object"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AttioListEntity",
      children: [jsx(_components.p, {
        children: "Schema for Attio List."
      }), jsx(_components.p, {
        children: "Lists are custom collections that can organize any type of record."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.attio.com/rest-api/endpoint-reference/lists",
          children: "https://docs.attio.com/rest-api/endpoint-reference/lists"
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
              children: "workspace_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the workspace this list belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_object"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent object type if applicable"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AttioRecordEntity",
      children: [jsx(_components.p, {
        children: "Schema for Attio Record."
      }), jsx(_components.p, {
        children: "Records are individual entries in Objects or Lists (e.g., a specific company, person, or deal)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.attio.com/rest-api/endpoint-reference/records",
          children: "https://docs.attio.com/rest-api/endpoint-reference/records"
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
              children: "object_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the object this record belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "list_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the list this record belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_object_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the parent object/list"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the record"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email_addresses"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Email addresses associated with this record"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "phone_numbers"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Phone numbers associated with this record"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "domains"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Domain names (for company records)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "categories"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Categories/tags for this record"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attributes"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Custom attributes and their values"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view this record in Attio"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AttioNoteEntity",
      children: [jsx(_components.p, {
        children: "Schema for Attio Note."
      }), jsx(_components.p, {
        children: "Notes are text entries attached to records for context and collaboration."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.attio.com/rest-api/endpoint-reference/notes",
          children: "https://docs.attio.com/rest-api/endpoint-reference/notes"
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
              children: "parent_record_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the record this note is attached to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_object"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of parent object"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the note"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Content of the note"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "format"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Format of the note (plaintext, markdown, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "User who created this note"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view this note in Attio"
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
