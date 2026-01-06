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
        alt: "Clickup logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Clickup"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "ClickUp source connector integrates with the ClickUp API to extract and synchronize data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your ClickUp workspaces."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing workspaces, spaces, folders, lists, tasks, and comments."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/clickup.py",
      children: jsx(_components.p, {
        children: "Explore the Clickup connector implementation"
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
      title: "ClickUpWorkspaceEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp workspace entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetAuthorizedTeams/",
          children: "https://clickup.com/api/clickupreference/operation/GetAuthorizedTeams/"
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
              children: "Workspace color"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "avatar"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Workspace avatar URL"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "members"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of workspace members"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpSpaceEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp space entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetSpaces/",
          children: "https://clickup.com/api/clickupreference/operation/GetSpaces/"
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
              children: "private"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the space is private"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Space status configuration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "multiple_assignees"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether multiple assignees are allowed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "features"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Space features configuration"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpFolderEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp folder entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetFolders/",
          children: "https://clickup.com/api/clickupreference/operation/GetFolders/"
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
              children: "hidden"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the folder is hidden"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent space ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "task_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of tasks in the folder"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpListEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp list entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetLists/",
          children: "https://clickup.com/api/clickupreference/operation/GetLists/"
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
              children: "folder_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent folder ID (optional)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent space ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "List content/description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List status configuration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "priority"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List priority configuration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "List assignee username"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "task_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of tasks in the list"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "List due date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "List start date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "folder_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent folder name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent space name"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpTaskEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp task entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetTasks/",
          children: "https://clickup.com/api/clickupreference/operation/GetTasks/"
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
              children: "status"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Task status configuration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "priority"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Task priority configuration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignees"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of task assignees"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of task tags"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Task due date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Task start date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "time_estimate"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Estimated time in milliseconds"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "time_spent"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Time spent in milliseconds"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_fields"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of custom fields"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "list_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent list ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "folder_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent folder ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Parent space ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Task URL"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Task description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent task ID if this is a subtask"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp comment entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetTaskComments/",
          children: "https://clickup.com/api/clickupreference/operation/GetTaskComments/"
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
              children: "Parent task ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Comment author information"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "text_content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Comment text content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "resolved"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the comment is resolved"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Comment assignee information"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assigned_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "User who assigned the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reactions"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of reactions to the comment"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpSubtaskEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp subtask entities."
      }), jsx(_components.p, {
        children: "Supports nested subtasks where subtasks can have their own subtasks.\nThe parent_task_id points to the immediate parent (task or subtask)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://clickup.com/api/clickupreference/operation/GetTasks/",
          children: "https://clickup.com/api/clickupreference/operation/GetTasks/"
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
              children: "parent_task_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Immediate parent task/subtask ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Subtask status configuration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignees"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of subtask assignees"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Subtask due date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Subtask description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "nesting_level"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Nesting level (1 = direct subtask, 2 = nested subtask, etc.)"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ClickUpFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for ClickUp file attachments."
      }), jsx(_components.p, {
        children: "Represents files attached to ClickUp tasks."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://api.clickup.com/api/v2/task/%7Btask_id%7D",
          children: "https://api.clickup.com/api/v2/task/{task_id}"
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
              children: "ID of the task this file is attached to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "task_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the task this file is attached to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "version"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Version number of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Original title/name of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "extension"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "File extension"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "hidden"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the attachment is hidden"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent attachment ID if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "thumbnail_small"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL for small thumbnail"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "thumbnail_medium"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL for medium thumbnail"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "thumbnail_large"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL for large thumbnail"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_folder"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether this is a folder attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "total_comments"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of comments on this attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url_w_query"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL with query parameters"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url_w_host"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL with host parameters"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email_data"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Email data if attachment is from email"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "User who uploaded the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "resolved"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the attachment is resolved"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "resolved_comments"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of resolved comments"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "source"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Source type of the attachment (numeric)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attachment_type"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Type of the attachment (numeric)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "orientation"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Image orientation if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Parent task ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "deleted"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the attachment is deleted"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Workspace ID"
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
