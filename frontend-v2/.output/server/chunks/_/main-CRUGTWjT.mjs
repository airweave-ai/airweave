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
        alt: "Onenote logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Onenote"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Microsoft OneNote source connector integrates with the Microsoft Graph API."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from Microsoft OneNote including notebooks, sections, and pages."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to OneNote resources with proper token refresh\nand rate limiting."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/onenote.py",
      children: jsx(_components.p, {
        children: "Explore the Onenote connector implementation"
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
      title: "OneNoteNotebookEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft OneNote notebook."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/notebook",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/notebook"
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
              children: "display_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The name of the notebook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_default"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether this is the user's default notebook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_shared"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the notebook is shared with other users."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_role"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current user's role in the notebook (Owner, Contributor, Reader)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the notebook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the notebook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "links"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Links for opening the notebook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "self_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The endpoint URL where you can get details about the notebook."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OneNoteSectionGroupEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft OneNote section group."
      }), jsx(_components.p, {
        children: "Section groups are containers that can hold sections and other section groups."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/sectiongroup",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/sectiongroup"
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
              children: "notebook_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the notebook this section group belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_section_group_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent section group, if nested."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "display_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The name of the section group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the section group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the section group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sections_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The endpoint URL where you can get all the sections in the section group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "section_groups_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The endpoint URL where you can get all the section groups nested in this section group."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OneNoteSectionEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft OneNote section."
      }), jsx(_components.p, {
        children: "Sections contain pages and can belong to a notebook or section group."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/section",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/section"
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
              children: "notebook_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the notebook this section belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_section_group_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent section group, if any."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "display_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The name of the section."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_default"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether this is the user's default section."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the section."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the section."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pages_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The endpoint URL where you can get all the pages in the section."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OneNotePageFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft OneNote page as a file entity."
      }), jsx(_components.p, {
        children: "Pages are the actual content containers in OneNote.\nExtends FileEntity to leverage Airweave's HTML processing pipeline."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/onenotepage",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/onenotepage"
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
              children: "notebook_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the notebook this page belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "section_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the section this page belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The title of the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The URL for the page's HTML content."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "level"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The indentation level of the page (for hierarchical pages)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "order"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The order of the page within its parent section."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "links"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Links for opening the page in OneNote client or web."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_tags"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "User-defined tags associated with the page."
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
