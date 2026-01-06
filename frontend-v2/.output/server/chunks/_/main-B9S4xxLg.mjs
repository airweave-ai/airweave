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
        alt: "Trello logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Trello"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Trello source connector integrates with the Trello API using OAuth1."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Trello boards and syncs boards, lists, cards, checklists, and members."
    }), "\n", jsx(_components.p, {
      children: "Note: Trello uses OAuth1.0, not OAuth2."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/trello.py",
      children: jsx(_components.p, {
        children: "Explore the Trello connector implementation"
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
      title: "TrelloBoardEntity",
      children: [jsx(_components.p, {
        children: "Schema for Trello board entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/trello/rest/api-group-boards/",
          children: "https://developer.atlassian.com/cloud/trello/rest/api-group-boards/"
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
              children: "trello_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Trello's unique identifier for the board"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "desc"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the board"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "closed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the board is closed/archived"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to the board"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "short_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Short URL to the board"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "prefs"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Board preferences and settings"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_organization"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the organization this board belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pinned"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the board is pinned"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TrelloListEntity",
      children: [jsx(_components.p, {
        children: "Schema for Trello list entities (columns on a board)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/trello/rest/api-group-lists/",
          children: "https://developer.atlassian.com/cloud/trello/rest/api-group-lists/"
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
              children: "trello_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Trello's unique identifier for the list"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_board"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board this list belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the board this list belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "closed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the list is archived"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pos"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Position of the list on the board"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "subscribed"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the user is subscribed to this list"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TrelloCardEntity",
      children: [jsx(_components.p, {
        children: "Schema for Trello card entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/trello/rest/api-group-cards/",
          children: "https://developer.atlassian.com/cloud/trello/rest/api-group-cards/"
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
              children: "trello_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Trello's unique identifier for the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "desc"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description/notes on the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_board"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board this card belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the board"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_list"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the list this card belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "list_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the list"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "closed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the card is archived"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Due date for the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_complete"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the due date is marked complete"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "date_last_activity"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Last activity date on the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_members"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "List of member IDs assigned to this card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "members"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Members assigned to this card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_labels"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "List of label IDs attached to this card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "labels"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Labels attached to this card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_checklists"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "List of checklist IDs on this card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "badges"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Badge information (comments, attachments, votes, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pos"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Position of the card in the list"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "short_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Short link to the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "short_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Short URL to the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full URL to the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Start date for the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "subscribed"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the user is subscribed to this card"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TrelloChecklistEntity",
      children: [jsx(_components.p, {
        children: "Schema for Trello checklist entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/trello/rest/api-group-checklists/",
          children: "https://developer.atlassian.com/cloud/trello/rest/api-group-checklists/"
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
              children: "trello_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Trello's unique identifier for the checklist"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_board"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board this checklist belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_card"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the card this checklist belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "card_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pos"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Position of the checklist on the card"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "check_items"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of checklist items with their states"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TrelloMemberEntity",
      children: [jsx(_components.p, {
        children: "Schema for Trello member (user) entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/trello/rest/api-group-members/",
          children: "https://developer.atlassian.com/cloud/trello/rest/api-group-members/"
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
              children: "username"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The username of the member"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "trello_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Trello's unique identifier for the member"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "full_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full name of the member"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "initials"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Member's initials"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "avatar_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to the member's avatar"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "bio"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Member's bio"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to the member's profile"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "id_boards"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "List of board IDs the member belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "member_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of member (normal, admin, etc.)"
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
