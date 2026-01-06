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
        alt: "Outlook Mail logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Outlook Mail"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Outlook Mail source connector integrates with the Microsoft Graph API to extract email data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from Outlook mailboxes."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to mail folders, messages, and\nattachments with hierarchical folder organization and content processing capabilities."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/outlook_mail.py",
      children: jsx(_components.p, {
        children: "Explore the Outlook Mail connector implementation"
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
        children: "Outlook Mail configuration schema."
      }), jsx(ParamField, {
        path: "after_date",
        type: "Optional[str]",
        required: true,
        children: jsx(_components.p, {
          children: "Sync emails after this date (format: YYYY/MM/DD or YYYY-MM-DD)."
        })
      }), jsx(ParamField, {
        path: "included_folders",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "Well-known folder names to include (e.g., 'inbox', 'sentitems', 'drafts'). Defaults to inbox and sent items."
        })
      }), jsx(ParamField, {
        path: "excluded_folders",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "Well-known folder names to exclude (e.g., 'junkemail', 'deleteditems'). Defaults to junk email and deleted items."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "OutlookMailFolderEntity",
      children: [jsx(_components.p, {
        children: "Schema for an Outlook mail folder."
      }), jsxs(_components.p, {
        children: ["See:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0"
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
              children: "Display name of the mail folder (e.g., 'Inbox')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_folder_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent mail folder, if any."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "child_folder_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of child mail folders under this folder."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "total_item_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Total number of items (messages) in this folder."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "unread_item_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of unread items in this folder."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "well_known_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Well-known name of this folder if applicable (e.g., 'inbox')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OutlookMessageEntity",
      children: [jsx(_components.p, {
        children: "Schema for Outlook message entities."
      }), jsxs(_components.p, {
        children: ["Reference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0"
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
              children: "folder_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the folder containing this message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "subject"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Subject line of the message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sender"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Email address of the sender"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "to_recipients"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Recipients of the message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "cc_recipients"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "CC recipients"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sent_date"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Date the message was sent"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "received_date"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Date the message was received"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body_preview"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Brief snippet of the message content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_read"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the message has been read"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_draft"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the message is a draft"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "importance"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Importance level (Low, Normal, High)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_attachments"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the message has attachments"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "internet_message_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Internet message ID"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OutlookAttachmentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Outlook attachment entities."
      }), jsxs(_components.p, {
        children: ["Reference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0"
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
              children: "message_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the message this attachment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attachment_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Outlook's attachment ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Content type of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_inline"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this is an inline attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Content ID for inline attachments"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Additional metadata about the attachment"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OutlookMessageDeletionEntity",
      children: [jsx(_components.p, {
        children: "Deletion signal for an Outlook message."
      }), jsxs(_components.p, {
        children: ["Emitted when the Graph delta API reports a message was removed.\nThe ", jsx(_components.code, {
          children: "entity_id"
        }), " matches the original message's id so downstream deletion\ncan target the correct parent/children."]
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
        }), jsx(_components.tbody, {
          children: jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "message_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the deleted message"
            })]
          })
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OutlookMailFolderDeletionEntity",
      children: [jsx(_components.p, {
        children: "Deletion signal for an Outlook mail folder."
      }), jsxs(_components.p, {
        children: ["Emitted when the Graph delta API reports a folder was removed.\nThe ", jsx(_components.code, {
          children: "entity_id"
        }), " matches the original folder's id."]
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
        }), jsx(_components.tbody, {
          children: jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "folder_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the deleted folder"
            })]
          })
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
