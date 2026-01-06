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
        alt: "Teams logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Teams"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Microsoft Teams source connector integrates with the Microsoft Graph API."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from Microsoft Teams including teams, channels, chats, and messages."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to Teams resources with proper token refresh\nand rate limiting."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/teams.py",
      children: jsx(_components.p, {
        children: "Explore the Teams connector implementation"
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
      title: "TeamsUserEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Teams user."
      }), jsxs(_components.p, {
        children: ["Based on the Microsoft Graph user resource.\nReference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/user",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/user"
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
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name displayed in the address book for the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_principal_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsxs(_components.td, {
              children: ["The user principal name (UPN) of the user (e.g., ", jsx(_components.a, {
                href: "mailto:user@contoso.com",
                children: "user@contoso.com"
              }), ")."]
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mail"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The SMTP address for the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "job_title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The user's job title."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "department"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The department in which the user works."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "office_location"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The office location in the user's place of business."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TeamsTeamEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Teams team."
      }), jsxs(_components.p, {
        children: ["Based on the Microsoft Graph team resource.\nReference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/team",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/team"
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
              children: "The name of the team."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "An optional description for the team."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "visibility"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The visibility of the group and team (Public, Private, HiddenMembership)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_archived"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether this team is in read-only mode."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A hyperlink that goes to the team in Microsoft Teams."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "classification"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Classification for the team (e.g., low, medium, high business impact)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "specialization"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Indicates whether the team is intended for a particular use case."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "internal_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A unique ID for the team used in audit logs."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TeamsChannelEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Teams channel."
      }), jsxs(_components.p, {
        children: ["Based on the Microsoft Graph channel resource.\nReference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/channel",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/channel"
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
              children: "team_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the team this channel belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "display_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Channel name as it appears to users."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Optional textual description for the channel."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The email address for sending messages to the channel."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "membership_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The type of the channel (standard, private, shared)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_archived"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the channel is archived."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_favorite_by_default"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the channel is recommended for all team members."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A hyperlink that goes to the channel in Microsoft Teams."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TeamsChatEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Teams chat (1:1, group, or meeting chat)."
      }), jsxs(_components.p, {
        children: ["Based on the Microsoft Graph chat resource.\nReference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/chat",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/chat"
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
              children: "chat_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Type of chat (oneOnOne, group, meeting)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "topic"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Subject or topic for the chat (only for group chats)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The URL for the chat in Microsoft Teams."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TeamsMessageEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Teams message (in channel or chat)."
      }), jsxs(_components.p, {
        children: ["Based on the Microsoft Graph chatMessage resource.\nReference: ", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/chatmessage",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/chatmessage"
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
              children: "team_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the team (if this is a channel message)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "channel_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the channel (if this is a channel message)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "chat_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the chat (if this is a chat message)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reply_to_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent message (for replies)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "message_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of message (message, chatEvent, systemEventMessage)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "subject"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The subject of the chat message."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body_content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The content of the message body."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body_content_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The type of the content (html or text)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "from_user"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Details of the sender of the message."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_edited_datetime"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Timestamp when edits to the message were made."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "deleted_datetime"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Timestamp at which the message was deleted."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "importance"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The importance of the message (normal, high, urgent)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mentions"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of entities mentioned in the message."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attachments"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "References to attached objects like files, tabs, meetings."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reactions"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Reactions for this message (e.g., Like)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Link to the message in Microsoft Teams."
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
