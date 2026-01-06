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
        alt: "Gitlab logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Gitlab"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "GitLab source connector integrates with the GitLab REST API to extract data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your GitLab projects."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing projects, users, repository files, issues, and merge requests\nwith configurable filtering options for branches and file types."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/gitlab.py",
      children: jsx(_components.p, {
        children: "Explore the Gitlab connector implementation"
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
        children: "GitLab configuration schema."
      }), jsx(ParamField, {
        path: "project_id",
        type: "str",
        required: false,
        default: "",
        children: jsx(_components.p, {
          children: "Specific project ID to sync (e.g., '12345'). If empty, syncs all accessible projects."
        })
      }), jsx(ParamField, {
        path: "branch",
        type: "str",
        required: false,
        default: "",
        children: jsx(_components.p, {
          children: "Specific branch to sync (e.g., 'main', 'master'). If empty, uses the default branch."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "GitLabProjectEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitLab project (repository) entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.gitlab.com/ee/api/projects.html",
          children: "https://docs.gitlab.com/ee/api/projects.html"
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
              children: "path"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Project path"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "path_with_namespace"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Full path with namespace"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Project description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "default_branch"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Default branch of the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "visibility"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Project visibility level"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "topics"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Project topics/tags"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "namespace"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Project namespace information"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "star_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of stars"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "forks_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of forks"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "open_issues_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of open issues"
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
              children: "empty_repo"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the repository is empty"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Web URL to the project"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitLabUserEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitLab user entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.gitlab.com/ee/api/users.html",
          children: "https://docs.gitlab.com/ee/api/users.html"
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
              children: "User's username"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "User account state"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "avatar_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's avatar URL"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "User's profile URL"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "bio"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's biography"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "location"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's location"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "public_email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's public email"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organization"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "job_title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's job title"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pronouns"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User's pronouns"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitLabDirectoryEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitLab directory entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.gitlab.com/ee/api/repositories.html",
          children: "https://docs.gitlab.com/ee/api/repositories.html"
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
              children: "path"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Path of the directory within the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the project containing this directory"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_path"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Path of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Web URL to the directory"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitLabCodeFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitLab code file entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.gitlab.com/ee/api/repository_files.html",
          children: "https://docs.gitlab.com/ee/api/repository_files.html"
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
              children: "blob_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Blob ID of the file content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_path"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Path of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "line_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of lines in the file"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitLabIssueEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitLab issue entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.gitlab.com/ee/api/issues.html",
          children: "https://docs.gitlab.com/ee/api/issues.html"
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
              children: "title"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Issue title"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Issue description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Issue state (opened, closed)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "closed_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Issue close timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "labels"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Issue labels"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Issue author information"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignees"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Issue assignees"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "milestone"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Issue milestone"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "iid"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Internal issue ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Web URL to the issue"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_notes_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of user notes/comments"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "upvotes"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of upvotes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "downvotes"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of downvotes"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitLabMergeRequestEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitLab merge request entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://docs.gitlab.com/ee/api/merge_requests.html",
          children: "https://docs.gitlab.com/ee/api/merge_requests.html"
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
              children: "title"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Merge request title"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Merge request description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Merge request state (opened, closed, merged)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "merged_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Merge request merge timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "closed_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Merge request close timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "labels"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Merge request labels"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Merge request author information"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignees"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Merge request assignees"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reviewers"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Merge request reviewers"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "source_branch"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Source branch name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "target_branch"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Target branch name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "milestone"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Merge request milestone"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "project_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the project"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "iid"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Internal merge request ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Web URL to the merge request"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "merge_status"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Merge status (can_be_merged, cannot_be_merged)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "draft"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the merge request is a draft"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "work_in_progress"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the merge request is work in progress"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "upvotes"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of upvotes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "downvotes"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of downvotes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_notes_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of user notes/comments"
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
