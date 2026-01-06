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
    ol: "ol",
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
        alt: "Google Docs logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Google Docs"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Google Docs source connector integrates with Google Drive API to extract Google Docs."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Google Drive account to retrieve Google Docs documents.\nDocuments are exported as DOCX and processed through Airweave's file\nprocessing pipeline to enable full-text semantic search across document content."
    }), "\n", jsx(_components.p, {
      children: "The connector handles:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Document listing and filtering"
      }), "\n", jsx(_components.li, {
        children: "Content export and download (DOCX format)"
      }), "\n", jsx(_components.li, {
        children: "Metadata preservation (ownership, sharing, timestamps)"
      }), "\n", jsx(_components.li, {
        children: "Incremental sync via Drive Changes API"
      }), "\n"]
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/google_docs.py",
      children: jsx(_components.p, {
        children: "Explore the Google Docs connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses ", jsx(_components.strong, {
        children: "OAuth 2.0 with custom credentials"
      }), ". You need to provide your OAuth application's Client ID and Client Secret, then complete the OAuth consent flow."]
    }), "\n", jsx(Card, {
      title: "OAuth Setup Required",
      className: "auth-setup-card",
      style: {
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: jsxs(_components.ol, {
        children: ["\n", jsx(_components.li, {
          children: "Create an OAuth application in your provider's developer console"
        }), "\n", jsx(_components.li, {
          children: "Enter your Client ID and Client Secret when configuring the connection"
        }), "\n", jsx(_components.li, {
          children: "Complete the OAuth consent flow"
        }), "\n"]
      })
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "The following configuration options are available for this connector:"
    }), "\n", jsxs(Card, {
      title: "Configuration Parameters",
      className: "config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.05)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "Google Docs configuration schema."
      }), jsx(ParamField, {
        path: "include_trashed",
        type: "bool",
        required: false,
        default: false,
        children: jsx(_components.p, {
          children: "Include documents that have been moved to trash. Defaults to False."
        })
      }), jsx(ParamField, {
        path: "include_shared",
        type: "bool",
        required: false,
        default: true,
        children: jsx(_components.p, {
          children: "Include documents shared with you by others. Defaults to True."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "GoogleDocsDocumentEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Google Docs document."
      }), jsx(_components.p, {
        children: "Represents a Google Doc file retrieved via the Google Drive API.\nThe document content is exported as DOCX and processed through\nAirweave's file processing pipeline to create searchable chunks."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.google.com/drive/api/v3/reference/files",
          children: "https://developers.google.com/drive/api/v3/reference/files"
        }), "\n", jsx(_components.a, {
          href: "https://developers.google.com/drive/api/guides/manage-downloads",
          children: "https://developers.google.com/drive/api/guides/manage-downloads"
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
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Display title of the document (without .docx extension)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Optional description of the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "starred"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user has starred this document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "trashed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the document is in the trash."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "explicitly_trashed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the document was explicitly trashed by the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shared"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the document is shared with others."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shared_with_me_time"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Time when this document was shared with the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sharing_user"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "User who shared this document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owners"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Owners of the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permissions"
            }), jsx(_components.td, {
              children: "Optional[List[Dict[str, Any]]]"
            }), jsx(_components.td, {
              children: "Permissions for this document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parents"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "IDs of parent folders containing this document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_view_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Link to open the document in Google Docs editor."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Link to the document's icon."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_time"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the document was created."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "modified_time"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the document was last modified."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "modified_by_me_time"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Last time the user modified the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "viewed_by_me_time"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Last time the user viewed the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "version"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Version number of the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "export_mime_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "MIME type used for exporting the document content (DOCX)."
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
