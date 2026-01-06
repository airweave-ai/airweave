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
        alt: "Asana logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Asana"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Asana source connector integrates with the Asana API to extract and synchronize data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Asana workspaces."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing workspaces, projects, tasks, sections, comments, and file attachments."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/asana.py",
      children: jsx(_components.p, {
        children: "Explore the Asana connector implementation"
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
      title: "AsanaWorkspaceEntity",
      children: [jsx(_components.p, {
        children: "Schema for Asana workspace entities."
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
              children: "is_organization"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the workspace is an organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email_domains"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "List of email domains that can access this workspace"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to access the workspace in the Asana application"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AsanaProjectEntity",
      children: [jsx(_components.p, {
        children: "Schema for Asana project entities."
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
              children: "workspace_gid"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Globally unique identifier of the workspace the project belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The name of the workspace the project belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Color of the project (e.g. 'dark-pink', 'light-blue')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the project is archived"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "current_status"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "The current status update for this project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "default_view"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The default view of the project (list, board, calendar, timeline)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The day on which this project is due (YYYY-MM-DD format)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_on"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The day on which this project is due (YYYY-MM-DD format)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "html_notes"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML formatted note content of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "notes"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Free-form textual information associated with the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_public"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the project is public to its team"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_on"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The day on which this project starts (YYYY-MM-DD format)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "The owner of this project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "The team that this project is associated with"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "members"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of users who are members of this project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "followers"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of users following this project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_fields"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of custom field values applied to the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_field_settings"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of custom field settings for this project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "default_access_level"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Default access level for the project (editor, commenter, viewer)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The icon for a project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to access the project in the Asana application"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AsanaSectionEntity",
      children: [jsx(_components.p, {
        children: "Schema for Asana section entities."
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
              children: "project_gid"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Globally unique identifier of the project this section belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "projects"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Deprecated. Array of projects this section is associated with"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AsanaTaskEntity",
      children: [jsx(_components.p, {
        children: "Schema for Asana task entities."
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
              children: "project_gid"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Globally unique identifier of the project this task belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "section_gid"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Globally unique identifier of the section this task belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "actual_time_minutes"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The actual time spent on this task in minutes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "approval_status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The status of the task's approval, if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User to which this task is assigned"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee_status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The scheduling status of this task for the user it's assigned to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "completed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the task is marked complete"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "completed_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time at which this task was completed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "completed_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "The user who completed this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "dependencies"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of tasks that this task depends on"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "dependents"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of tasks that depend on this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time at which this task is due with a time component"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_on"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The date on which this task is due (YYYY-MM-DD format)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "external"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Information about the external application syncing with this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "html_notes"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML formatted note content of the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "notes"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Free-form textual information associated with the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_rendered_as_separator"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the task is rendered as a separator in list view"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "liked"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the task is liked by the authorized user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "memberships"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of projects and sections this task is in"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "num_likes"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "The number of users who have liked this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "num_subtasks"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "The number of subtasks on this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "The parent of this task, if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to access the task in the Asana application"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "resource_subtype"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The subtype of the task (default_task, milestone, approval)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time at which this task starts with a time component"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_on"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The date on which this task starts (YYYY-MM-DD format)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of tags associated with this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_fields"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of custom field values applied to the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "followers"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Array of users following this task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "The workspace this task is associated with"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AsanaCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Asana comment/story entities."
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
              children: "task_gid"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Globally unique identifier of the task this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author"
            }), jsx(_components.td, {
              children: "Dict"
            }), jsx(_components.td, {
              children: "The user who created this comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "resource_subtype"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The subtype of the comment resource"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "text"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The plain text content of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "html_text"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML formatted content of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_pinned"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the comment is pinned to the task"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_edited"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the comment has been edited"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sticker_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name of the sticker (for sticker comments)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "num_likes"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "The number of users who have liked this comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "liked"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the comment is liked by the authorized user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The type of the comment (comment or system)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "previews"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Previews of attachments referenced in the comment"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "AsanaFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for Asana file attachments."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.asana.com/reference/getattachment",
          children: "https://developers.asana.com/reference/getattachment"
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
              children: "task_gid"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "GID of the task this file is attached to"
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
              children: "resource_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Type of the attachment resource"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "host"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Service hosting the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Parent resource the attachment is on"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "view_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permanent"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this is a permanent attachment"
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
