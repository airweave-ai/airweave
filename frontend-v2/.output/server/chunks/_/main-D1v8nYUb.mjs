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
    ol: "ol",
    p: "p",
    pre: "pre",
    strong: "strong",
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
        alt: "Gmail logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Gmail"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Gmail source connector integrates with the Gmail API to extract and synchronize email data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Gmail account."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing email threads, individual messages, and file attachments."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/gmail.py",
      children: jsx(_components.p, {
        children: "Explore the Gmail connector implementation"
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
        children: "Gmail configuration schema."
      }), jsx(ParamField, {
        path: "after_date",
        type: "Optional[str]",
        required: true,
        children: jsx(_components.p, {
          children: "Sync emails after this date (format: YYYY/MM/DD or YYYY-MM-DD)."
        })
      }), jsx(ParamField, {
        path: "included_labels",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "Labels to include (e.g., 'inbox', 'sent', 'important'). Defaults to inbox and sent."
        })
      }), jsx(ParamField, {
        path: "excluded_labels",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "Labels to exclude (e.g., 'spam', 'trash', 'promotions', 'social'). Defaults to spam and trash."
        })
      }), jsx(ParamField, {
        path: "excluded_categories",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "Gmail categories to exclude (e.g., 'promotions', 'social', 'updates', 'forums')."
        })
      }), jsx(ParamField, {
        path: "gmail_query",
        type: "Optional[str]",
        required: true,
        children: jsx(_components.p, {
          children: "Advanced. Custom Gmail query string (overrides all other filters if provided)."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "GmailThreadEntity",
      children: [jsx(_components.p, {
        children: "Schema for Gmail thread entities."
      }), jsxs(_components.p, {
        children: ["Reference: ", jsx(_components.a, {
          href: "https://developers.google.com/gmail/api/reference/rest/v1/users.threads",
          children: "https://developers.google.com/gmail/api/reference/rest/v1/users.threads"
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
              children: "snippet"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A short snippet from the thread"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "history_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The thread's history ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "message_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of messages in the thread"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "label_ids"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Labels applied to this thread"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GmailMessageEntity",
      children: [jsx(_components.p, {
        children: "Schema for Gmail message entities."
      }), jsxs(_components.p, {
        children: ["Reference: ", jsx(_components.a, {
          href: "https://developers.google.com/gmail/api/reference/rest/v1/users.messages",
          children: "https://developers.google.com/gmail/api/reference/rest/v1/users.messages"
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
              children: "thread_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the thread this message belongs to"
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
              children: "to"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Recipients of the message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "cc"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "CC recipients"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "bcc"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "BCC recipients"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "date"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Date the message was sent"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "snippet"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Brief snippet of the message content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "label_ids"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Labels applied to this message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "internal_date"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Internal Gmail timestamp"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GmailAttachmentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Gmail attachment entities."
      }), jsxs(_components.p, {
        children: ["Reference: ", jsx(_components.a, {
          href: "https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments",
          children: "https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments"
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
              children: "Gmail's attachment ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "thread_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the thread containing the message"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GmailMessageDeletionEntity",
      children: [jsx(_components.p, {
        children: "Deletion signal for a Gmail message."
      }), jsxs(_components.p, {
        children: ["Emitted when the Gmail History API reports a messageDeleted. The entity_id matches the\nmessage entity's ID format (msg_", message_id, ") so downstream deletion removes the\ncorrect parent/children."]
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
              children: "The Gmail message ID that was deleted"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "thread_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Thread ID (optional if not provided by change record)"
            })]
          })]
        })]
      })]
    }), "\n", "\n", jsx(_components.h2, {
      children: "Integrate Airweave with Google APIs on localhost"
    }), "\n", jsxs(_components.p, {
      children: ["This guide will walk you through connecting Google Workspace APIs to Airweave when running locally.\nGoogle provides extensive ", jsx(_components.a, {
        href: "https://developers.google.com/workspace/guides/get-started",
        children: "documentation"
      }), " on setting up your workspace.\nBelow is a streamlined process for connecting Google APIs to Airweave."]
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/create-project",
          children: "Create a Google Cloud project"
        }), " for your Google Workspace (if you don't already have one)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/enable-apis",
          children: "Enable the Google Workspace APIs"
        }), " for Gmail, Google Calendar, and Google Drive"]
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/configure-oauth-consent",
          children: "Configure Google OAuth 2.0 consent screen"
        })
      }), "\n", jsxs(_components.li, {
        children: ["Under ", jsx(_components.code, {
          children: "Audience"
        }), ", select ", jsx(_components.code, {
          children: "Make external"
        }), " and add test users"]
      }), "\n", jsxs(_components.li, {
        children: ["Under ", jsx(_components.code, {
          children: "Data Access"
        }), ", add the following scopes:"]
      }), "\n"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "https://www.googleapis.com/auth/docs\nhttps://www.googleapis.com/auth/drive.photos.readonly\nhttps://www.googleapis.com/auth/drive\nhttps://www.googleapis.com/auth/drive.readonly\nhttps://www.googleapis.com/auth/drive.metadata\nhttps://www.googleapis.com/auth/drive.metadata.readonly\nhttps://www.googleapis.com/auth/gmail.readonly\nhttps://www.googleapis.com/auth/calendar.events.public.readonly\nhttps://www.googleapis.com/auth/calendar.freebusy\nhttps://www.googleapis.com/auth/calendar.readonly\nhttps://www.googleapis.com/auth/calendar.calendars.readonly\nhttps://www.googleapis.com/auth/calendar.events.owned.readonly\nhttps://www.googleapis.com/auth/calendar.events.readonly\n"
      })
    }), "\n", jsxs(_components.ol, {
      start: "6",
      children: ["\n", jsxs(_components.li, {
        children: ["\n", jsx(_components.p, {
          children: jsx(_components.a, {
            href: "https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",
            children: "Create OAuth client ID credentials"
          })
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsx(_components.p, {
          children: 'Under "Authorized redirect URIs," click "+ Add URI" and add the Redirect URI. Use the appropriate URL for your environment:'
        }), "\n", jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Production (Airweave Cloud):"
          })
        }), "\n", jsx(_components.pre, {
          children: jsx(_components.code, {
            children: "https://api.airweave.ai/source-connections/callback\n"
          })
        }), "\n", jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Local:"
          })
        }), "\n", jsx(_components.pre, {
          children: jsx(_components.code, {
            children: "http://localhost:8001/source-connections/callback\n"
          })
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: ["Locate the client ID and client secret from your newly created OAuth client. Add these credentials to the ", jsx(_components.code, {
            children: "dev.integrations.yml"
          }), " file to enable Google API integration."]
        }), "\n"]
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
function _missingMdxReference(id, component) {
  throw new Error("Expected component `" + id + "` to be defined: you likely forgot to import, pass, or provide it.");
}
export {
  MDXContent as default
};
