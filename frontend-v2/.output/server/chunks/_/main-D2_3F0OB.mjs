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
        alt: "Bitbucket logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Bitbucket"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Bitbucket source connector integrates with the Bitbucket REST API to extract data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Bitbucket workspaces and repositories."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing workspaces, repositories, directories,\nand code files with configurable filtering options for branches and file types."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/bitbucket.py",
      children: jsx(_components.p, {
        children: "Explore the Bitbucket connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsx(_components.p, {
      children: "This connector uses a custom authentication configuration."
    }), "\n", jsxs(Card, {
      title: "Authentication Configuration",
      className: "auth-config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "Bitbucket authentication credentials schema."
      }), jsx(_components.p, {
        children: "Requires API token authentication with Atlassian email."
      }), jsxs(ParamField, {
        path: "access_token",
        type: "str",
        required: true,
        children: [jsxs(_components.p, {
          children: ["Create a Bitbucket API token ", jsx(_components.a, {
            href: "https://id.atlassian.com/manage-profile/security/api-tokens",
            children: "here"
          }), " with scopes:"]
        }), jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: "account"
          }), "\n", jsx(_components.li, {
            children: "read:user:bitbucket"
          }), "\n", jsx(_components.li, {
            children: "read:workspace:bitbucket"
          }), "\n", jsx(_components.li, {
            children: "read:repository:bitbucket"
          }), "\n"]
        }), jsx(_components.p, {
          children: "When using this, also provide your Atlassian email address."
        })]
      }), jsx(ParamField, {
        path: "email",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Your Atlassian email address (required for API token authentication)"
        })
      }), jsx(ParamField, {
        path: "workspace",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Bitbucket workspace slug (e.g., 'my-workspace')"
        })
      }), jsx(ParamField, {
        path: "repo_slug",
        type: "Optional[str]",
        required: false,
        default: "",
        children: jsx(_components.p, {
          children: "Specific repository to sync (e.g., 'my-repo'). If empty, syncs all repositories in the workspace."
        })
      })]
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
        children: "Bitbucket configuration schema."
      }), jsx(ParamField, {
        path: "branch",
        type: "str",
        required: false,
        default: "",
        children: jsx(_components.p, {
          children: "Specific branch to sync (e.g., 'main', 'develop'). If empty, uses the default branch."
        })
      }), jsx(ParamField, {
        path: "file_extensions",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "List of file extensions to include (e.g., '.py', '.js', '.md'). If empty, includes all text files."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "BitbucketWorkspaceEntity",
      children: [jsx(_components.p, {
        children: "Schema for Bitbucket workspace entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-workspaces/",
          children: "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-workspaces/"
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
              children: "slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Workspace slug identifier"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "uuid"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Workspace UUID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_private"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the workspace is private"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the workspace"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BitbucketRepositoryEntity",
      children: [jsx(_components.p, {
        children: "Schema for Bitbucket repository entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/",
          children: "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/"
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
              children: "slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Repository slug"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "full_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Full repository name including workspace"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Repository description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_private"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the repository is private"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fork_policy"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Fork policy of the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "language"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Primary language of the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "size"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Size of the repository in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mainbranch"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Main branch name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace_slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Slug of the parent workspace"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the repository"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BitbucketDirectoryEntity",
      children: [jsx(_components.p, {
        children: "Schema for Bitbucket directory entity."
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
              children: "repo_slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Slug of the repository containing this directory"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "repo_full_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Full name of the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace_slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Slug of the workspace"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the directory"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BitbucketCodeFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for Bitbucket code file entity."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/",
          children: "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/"
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
              children: "commit_hash"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Commit hash of the file version"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "repo_slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Slug of the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "repo_full_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Full name of the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workspace_slug"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Slug of the workspace"
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
