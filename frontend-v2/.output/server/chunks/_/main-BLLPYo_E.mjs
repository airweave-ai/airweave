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
        alt: "Airtable logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Airtable"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Airtable source connector integrates with the Airtable API to extract and synchronize data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Airtable bases and syncs everything by default:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "User info (authenticated user)"
      }), "\n", jsx(_components.li, {
        children: "All accessible bases"
      }), "\n", jsx(_components.li, {
        children: "All tables in each base"
      }), "\n", jsx(_components.li, {
        children: "All records in each table"
      }), "\n", jsx(_components.li, {
        children: "All comments on each record"
      }), "\n", jsx(_components.li, {
        children: "All attachments in each record"
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "No configuration needed - just connect and sync!"
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/airtable.py",
      children: jsx(_components.p, {
        children: "Explore the Airtable connector implementation"
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
      title: "AirtableUserEntity",
      children: [jsx(_components.p, {
        children: "The authenticated user (from /meta/whoami endpoint)."
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
              children: "email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "scopes"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "OAuth scopes granted to the token"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AirtableBaseEntity",
      children: [jsx(_components.p, {
        children: "Metadata for an Airtable base."
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
              children: "permission_level"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Permission level for this base"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to open the base in Airtable"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AirtableTableEntity",
      children: [jsx(_components.p, {
        children: "Metadata for an Airtable table (schema-level info)."
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
              children: "base_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent base ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Table description, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fields_schema"
            }), jsx(_components.td, {
              children: "Optional[List[Dict[str, Any]]]"
            }), jsx(_components.td, {
              children: "List of field definitions from the schema API"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "primary_field_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the primary field"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "view_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of views in this table"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AirtableRecordEntity",
      children: [jsx(_components.p, {
        children: "One Airtable record (row) as a searchable chunk."
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
              children: "base_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent base ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "table_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent table ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "table_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent table name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fields"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Raw Airtable fields map"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AirtableCommentEntity",
      children: [jsx(_components.p, {
        children: "A comment on an Airtable record."
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
              children: "record_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent record ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "base_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent base ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "table_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent table ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "text"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Comment text"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Author user ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author_email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Author email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Author display name"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AirtableAttachmentEntity",
      children: [jsx(_components.p, {
        children: "Attachment file from an Airtable record."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://airtable.com/developers/web/api/field-model#multipleattachment",
          children: "https://airtable.com/developers/web/api/field-model#multipleattachment"
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
              children: "base_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Base ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "table_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Table ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "table_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Table name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "record_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Record ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "field_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Field name that contains this attachment"
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
