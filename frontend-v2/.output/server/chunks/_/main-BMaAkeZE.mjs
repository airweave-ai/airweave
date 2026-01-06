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
        alt: "Linear logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Linear"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Linear source connector integrates with the Linear GraphQL API to extract project data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Linear workspace."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to teams, projects, issues, and\nusers with advanced rate limiting and error handling for optimal performance."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/linear.py",
      children: jsx(_components.p, {
        children: "Explore the Linear connector implementation"
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
      title: "LinearIssueEntity",
      children: [jsx(_components.p, {
        children: "Schema for Linear issue entities."
      }), jsx(_components.p, {
        children: "This entity represents an issue from Linear, containing all relevant\nmetadata and content from the Linear API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
          children: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
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
              children: "identifier"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier of the issue (e.g., 'ENG-123')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The title of the issue"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The description/content of the issue"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "priority"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The priority level of the issue"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current state/status name of the issue"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "completed_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the issue was completed, if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The due date for the issue, if set"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the team this issue belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the team this issue belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the project this issue belongs to, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the project this issue belongs to, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the user assigned to this issue, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the issue in Linear"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "LinearAttachmentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Linear attachment entities."
      }), jsx(_components.p, {
        children: "Attachments in Linear allow linking external resources to issues."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
          children: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
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
              children: "issue_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the issue this attachment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "issue_identifier"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Identifier of the issue (e.g., 'ENG-123')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "subtitle"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Subtitle of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "source"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Source information about the attachment"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "LinearProjectEntity",
      children: [jsx(_components.p, {
        children: "Schema for Linear project entities."
      }), jsx(_components.p, {
        children: "This entity represents a project from Linear, containing all relevant\nmetadata and content from the Linear API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
          children: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
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
              children: "slug_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The project's unique URL slug"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The project's description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "priority"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The priority level of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current state/status name of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "completed_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the project was completed, if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "started_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the project was started, if applicable"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "target_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The estimated completion date of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The estimated start date of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_ids"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "IDs of the teams this project belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_names"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "Names of the teams this project belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "progress"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "The overall progress of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "lead"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the project lead, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the project in Linear"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "LinearTeamEntity",
      children: [jsx(_components.p, {
        children: "Schema for Linear team entities."
      }), jsx(_components.p, {
        children: "This entity represents a team from Linear, containing all relevant\nmetadata and content from the Linear API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
          children: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
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
              children: "key"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The team's unique key used in URLs"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The team's description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The team's color"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The icon of the team"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "private"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the team is private or not"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The timezone of the team"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent team, if this is a sub-team"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the parent team, if this is a sub-team"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "issue_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of issues in the team"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the team in Linear"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "LinearCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Linear comment entities."
      }), jsx(_components.p, {
        children: "This entity represents a comment on a Linear issue, containing all relevant\nmetadata and content from the Linear API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
          children: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
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
              children: "issue_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the issue this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "issue_identifier"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Identifier of the issue (e.g., 'ENG-123')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The content/body of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user who created the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the user who created the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the team this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the team this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the project this comment belongs to, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the project this comment belongs to, if any"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the comment in Linear"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "LinearUserEntity",
      children: [jsx(_components.p, {
        children: "Schema for Linear user entities."
      }), jsx(_components.p, {
        children: "This entity represents a user from Linear, containing all relevant\nmetadata and content from the Linear API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
          children: "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
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
              children: "The user's display name, unique within the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The user's email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "avatar_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to the user's avatar image"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A short description of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The local timezone of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "active"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the user account is active or disabled"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "admin"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the user is an organization administrator"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "guest"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the user is a guest with limited access"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_seen"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "The last time the user was seen online"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status_emoji"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The emoji to represent the user's current status"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status_label"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The label of the user's current status"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status_until_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date at which the user's status should be cleared"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_issue_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of issues created by the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_ids"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "IDs of the teams this user belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_names"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "Names of the teams this user belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the user in Linear"
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
