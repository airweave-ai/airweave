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
        alt: "Monday logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Monday"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Monday source connector integrates with the Monday.com GraphQL API to extract work data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Monday.com workspace."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to boards, items, and team\ncollaboration features with full relationship mapping and custom field support."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/monday.py",
      children: jsx(_components.p, {
        children: "Explore the Monday connector implementation"
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
      title: "MondayBoardEntity",
      children: [jsx(_components.p, {
        children: "Schema for Monday Board objects."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.monday.com/api-reference/reference/boards",
          children: "https://developer.monday.com/api-reference/reference/boards"
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
              children: "board_kind"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The board's kind/type: 'public', 'private', or 'share'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "columns"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "A list of columns on the board (each column is typically a dict of fields)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The description of the board."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "groups"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "A list of groups on the board (each group is typically a dict of fields)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owners"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "A list of users or teams who own the board."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The board's current state: 'active', 'archived', or 'deleted'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The unique identifier of the workspace containing this board (if any)."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "MondayGroupEntity",
      children: [jsx(_components.p, {
        children: "Schema for Monday Group objects."
      }), jsx(_components.p, {
        children: "Groups are collections of items (rows) within a board."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.monday.com/api-reference/reference/boards",
          children: "https://developer.monday.com/api-reference/reference/boards"
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
              children: "group_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier (ID) of the group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board this group belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title or display name of the group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Group color code (e.g., 'red', 'green', 'blue', etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this group is archived."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "items"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "List of items (rows) contained within this group."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "MondayColumnEntity",
      children: [jsx(_components.p, {
        children: "Schema for Monday Column objects."
      }), jsx(_components.p, {
        children: "Columns define the structure of data on a Monday board."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.monday.com/api-reference/reference/column-types-reference",
          children: "https://developer.monday.com/api-reference/reference/column-types-reference"
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
              children: "column_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier (ID) of the column."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board this column belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The display title of the column."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "column_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The type of the column (e.g., 'text', 'number', 'date', 'link')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The description of the column."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "settings_str"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Raw settings/configuration details for the column."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this column is archived or hidden."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "MondayItemEntity",
      children: [jsx(_components.p, {
        children: "Schema for Monday Item objects (rows on a board)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.monday.com/api-reference/reference/boards",
          children: "https://developer.monday.com/api-reference/reference/boards"
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
              children: "item_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier (ID) of the item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board this item belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "group_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the group this item is placed in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current state of the item: active, archived, or deleted."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "column_values"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "A list of column-value dicts that contain the data for each column."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "creator"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Information about the user/team who created this item."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "MondaySubitemEntity",
      children: [jsx(_components.p, {
        children: "Schema for Monday Subitem objects."
      }), jsx(_components.p, {
        children: "Subitems are items nested under a parent item, often in a dedicated 'Subitems' column."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.monday.com/api-reference/reference/boards",
          children: "https://developer.monday.com/api-reference/reference/boards"
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
              children: "subitem_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier (ID) of the subitem."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_item_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the parent item this subitem belongs to."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the board that this subitem resides in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "group_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the group this subitem is placed in."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current state of the subitem: active, archived, or deleted."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "column_values"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "A list of column-value dicts for each column on the subitem."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "creator"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Information about the user/team who created this subitem."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "MondayUpdateEntity",
      children: [jsx(_components.p, {
        children: "Schema for Monday Update objects."
      }), jsx(_components.p, {
        children: "monday.com updates add notes and discussions to items outside of their column data."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.monday.com/api-reference/reference/updates",
          children: "https://developer.monday.com/api-reference/reference/updates"
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
              children: "update_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier (ID) of the update."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the item this update is referencing (could also be a board-level update)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "board_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the board, if applicable."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "creator_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user who created this update."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The text (body) of the update, which may include markdown or HTML formatting."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assets"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Assets (e.g. images, attachments) associated with this update."
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
