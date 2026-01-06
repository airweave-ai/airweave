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
        alt: "Word logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Word"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Microsoft Word source connector integrates with the Microsoft Graph API."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes Word documents from Microsoft OneDrive and SharePoint.\nDocuments are processed through Airweave's file handling pipeline which:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Downloads the .docx/.doc file"
      }), "\n", jsx(_components.li, {
        children: "Converts to markdown for text extraction"
      }), "\n", jsx(_components.li, {
        children: "Chunks content for vector search"
      }), "\n", jsx(_components.li, {
        children: "Indexes for semantic search"
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to Word documents with proper token refresh\nand rate limiting."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/word.py",
      children: jsx(_components.p, {
        children: "Explore the Word connector implementation"
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
      title: "WordDocumentEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Word document as a file entity."
      }), jsx(_components.p, {
        children: "Represents Word documents (.docx, .doc) stored in OneDrive/SharePoint.\nExtends FileEntity to leverage Airweave's file processing pipeline which will:"
      }), jsxs(_components.ul, {
        children: ["\n", jsx(_components.li, {
          children: "Download the Word document"
        }), "\n", jsx(_components.li, {
          children: "Convert it to markdown using document converters"
        }), "\n", jsx(_components.li, {
          children: "Chunk the content for indexing"
        }), "\n"]
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/driveitem",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/driveitem"
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
              children: "str"
            }), jsx(_components.td, {
              children: "The title/name of the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to open the document in Word Online."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_download_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Direct download URL for the document content."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_reference"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the parent folder/drive location."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "drive_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the drive containing this document."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "folder_path"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full path to the parent folder."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the document if available."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shared"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about sharing status of the document."
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
