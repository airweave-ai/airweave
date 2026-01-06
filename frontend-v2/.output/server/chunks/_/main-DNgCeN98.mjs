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
        alt: "Confluence logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Confluence"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Confluence source connector integrates with the Confluence REST API to extract content."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Confluence instance."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing spaces, pages, blog posts, comments, labels, and other\ncontent types. It converts Confluence pages to HTML format for content extraction and\nextracts embedded files and attachments from page content."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/confluence.py",
      children: jsx(_components.p, {
        children: "Explore the Confluence connector implementation"
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
      title: "ConfluenceSpaceEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Space."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/",
          children: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/"
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
              children: "space_key"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Unique key for the space."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of space (e.g. 'global')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the space."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the space if applicable."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "homepage_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the homepage for this space."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluencePageEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Page."
      }), jsx(_components.p, {
        children: "Pages are treated as FileEntity with HTML body saved to local file.\nContent is not stored in entity fields, only in the downloaded file."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-pages/",
          children: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-pages/"
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
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Actual Confluence page ID."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the space this page belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML body or excerpt of the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "version"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Page version number."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the page (e.g., 'current')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceBlogPostEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Blog Post."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-blog-posts/",
          children: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-blog-posts/"
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
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Actual Confluence blog post ID."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the blog post."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the space this blog post is in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML body of the blog post."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "version"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Blog post version number."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the blog post (e.g., 'current')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Comment."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comments/",
          children: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comments/"
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
              children: "parent_content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the content this comment is attached to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "text"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Text/HTML body of the comment."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the user who created the comment."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the comment (e.g., 'current')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceDatabaseEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Database object."
      }), jsx(_components.p, {
        children: 'Note: The "database" content type in Confluence Cloud.'
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
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Actual Confluence database ID."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title or name of the database."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Space key for the database item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description or extra info about the DB."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the database content item."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceFolderEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Folder object."
      }), jsx(_components.p, {
        children: 'Note: The "folder" content type in Confluence Cloud.'
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
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Actual Confluence folder ID."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the folder."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Key of the space this folder is in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the folder (e.g., 'current')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceLabelEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Label object."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-labels/",
          children: "https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-labels/"
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
              children: "label_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of the label (e.g., 'global')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user or content that owns label."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceTaskEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Task object."
      }), jsx(_components.p, {
        children: "For example, tasks extracted from Confluence pages or macros."
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
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The content ID (page, blog, etc.) that this task is associated with."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Space key if task is associated with a space."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "text"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Text of the task."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the user assigned to this task."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "completed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates if this task is completed."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Due date/time if applicable."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceWhiteboardEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Whiteboard object."
      }), jsx(_components.p, {
        children: 'Note: The "whiteboard" content type in Confluence Cloud.'
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
              children: "Title of the whiteboard."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Key of the space this whiteboard is in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the whiteboard (e.g., 'current')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ConfluenceCustomContentEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Confluence Custom Content object."
      }), jsx(_components.p, {
        children: 'Note: The "custom content" type in Confluence Cloud.'
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
              children: "Title or name of this custom content."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Key of the space this content resides in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Optional HTML body or representation."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the custom content item (e.g., 'current')."
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
