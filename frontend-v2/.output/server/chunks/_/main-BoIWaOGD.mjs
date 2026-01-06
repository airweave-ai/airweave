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
        alt: "Todoist logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Todoist"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Todoist source connector integrates with the Todoist REST API to extract task data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Todoist workspace."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to projects, tasks, and\ncollaboration features with proper hierarchical organization and productivity insights."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/todoist.py",
      children: jsx(_components.p, {
        children: "Explore the Todoist connector implementation"
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
      title: "TodoistProjectEntity",
      children: [jsx(_components.p, {
        children: "Schema for Todoist project entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.todoist.com/rest/v2/#projects",
          children: "https://developer.todoist.com/rest/v2/#projects"
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
              children: "color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Color of the project (e.g., 'grey', 'blue')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "comment_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of comments in the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "order"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Project order in the project list"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_shared"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the project is shared with others"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_favorite"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the project is marked as a favorite"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_inbox_project"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this is the Inbox project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_team_inbox"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this is the team Inbox project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "view_style"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Project view style ('list' or 'board')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to access the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent project if nested"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TodoistSectionEntity",
      children: [jsx(_components.p, {
        children: "Schema for Todoist section entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.todoist.com/rest/v2/#sections",
          children: "https://developer.todoist.com/rest/v2/#sections"
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
              children: "project_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the project this section belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "order"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Section order in the project"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TodoistTaskEntity",
      children: [jsx(_components.p, {
        children: "Schema for Todoist task entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.todoist.com/rest/v2/#tasks",
          children: "https://developer.todoist.com/rest/v2/#tasks"
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
              children: "content"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The task content/title"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Optional detailed description of the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "comment_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of comments on the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_completed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the task is completed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "labels"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "List of label names attached to the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "order"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Task order in the project or section"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "priority"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Task priority (1-4, 4 is highest)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the project this task belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "section_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the section this task belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent task if subtask"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "creator_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user who created the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user assigned to the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assigner_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user who assigned the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Due date in YYYY-MM-DD format"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_datetime"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Due date and time"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_string"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Original due date string (e.g., 'tomorrow')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_is_recurring"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the task is recurring"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Timezone for the due date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "deadline_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Deadline date in YYYY-MM-DD format"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "duration_amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Duration amount"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "duration_unit"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Duration unit ('minute' or 'day')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to access the task"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "TodoistCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Todoist comment entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.todoist.com/rest/v2/#comments",
          children: "https://developer.todoist.com/rest/v2/#comments"
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
              children: "task_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the task this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The comment content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "posted_at"
            }), jsx(_components.td, {
              children: "Any"
            }), jsx(_components.td, {
              children: "When the comment was posted"
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
