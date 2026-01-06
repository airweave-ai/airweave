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
        alt: "Github logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Github"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "GitHub source connector integrates with the GitHub REST API to extract and synchronize data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your GitHub repositories."
    }), "\n", jsx(_components.p, {
      children: "It supports syncing repository metadata, directory structures, and code files with\nconfigurable filtering options for branches and file types."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/github.py",
      children: jsx(_components.p, {
        children: "Explore the Github connector implementation"
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
        children: "GitHub authentication credentials schema."
      }), jsx(ParamField, {
        path: "personal_access_token",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "GitHub PAT with read rights (code, contents, metadata) to the repository"
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
        children: "Github configuration schema."
      }), jsx(ParamField, {
        path: "repo_name",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Repository to sync in owner/repo format (e.g., 'airweave-ai/airweave')"
        })
      }), jsx(ParamField, {
        path: "branch",
        type: "str",
        required: false,
        default: "",
        children: jsx(_components.p, {
          children: "Specific branch to sync (e.g., 'main', 'development'). If empty, uses the default branch."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "GitHubRepositoryEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitHub repository entity."
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
              children: "full_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Full repository name including owner"
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
              children: "default_branch"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Default branch of the repository"
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
              children: "fork"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the repository is a fork"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "size"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Size of the repository in KB"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "stars_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of stars"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "watchers_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of watchers"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "forks_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of forks"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "open_issues_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of open issues"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitHubDirectoryEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitHub directory entity."
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
              children: "repo_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the repository containing this directory"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "repo_owner"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Owner of the repository"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitHubCodeFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitHub code file entity."
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
              children: "sha"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "SHA hash of the file content"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "line_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of lines in the file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_binary"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Flag indicating if file is binary"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GithubRepoEntity",
      children: [jsx(_components.p, {
        children: "Schema for a GitHub repository (alternative schema)."
      }), jsxs(_components.p, {
        children: ["References:\n", jsx(_components.a, {
          href: "https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28",
          children: "https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28"
        })]
      }), jsx(_components.p, {
        children: "Note: This is an alternative repository entity schema. Consider using GitHubRepositoryEntity."
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
              children: "full_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full name (including owner) of the repo."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner_login"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Login/username of the repository owner."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "private"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the repository is private."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Short description of the repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fork"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this repository is a fork."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pushed_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "When the repository was last pushed."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "homepage"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Homepage URL for the repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "size"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Size of the repository (in kilobytes)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "stargazers_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of stars on this repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "watchers_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of people watching this repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "language"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Primary language of the repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "forks_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of forks for this repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "open_issues_count"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Number of open issues on this repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "topics"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Topics/tags applied to this repo."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "default_branch"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Default branch name of the repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the repository is archived."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "disabled"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the repository is disabled in GitHub."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GithubContentEntity",
      children: [jsx(_components.p, {
        children: "Schema for a GitHub repository's content (file, directory, submodule, etc.)."
      }), jsxs(_components.p, {
        children: ["References:\n", jsx(_components.a, {
          href: "https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28",
          children: "https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28"
        })]
      }), jsx(_components.p, {
        children: "Note: This is a generic content entity. Consider using specific entities like\nGitHubCodeFileEntity or GitHubDirectoryEntity."
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
              children: "repo_full_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full name of the parent repository."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "path"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Path of the file or directory within the repo."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sha"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "SHA identifier for this content item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of content. Typically 'file', 'dir', 'submodule', or 'symlink'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "size"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Size of the content (in bytes)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "html_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML URL for viewing this content on GitHub."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "download_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Direct download URL if applicable."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "File content (base64-encoded) if retrieved via 'mediaType=raw' or similar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "encoding"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Indicates the encoding of the content (e.g., 'base64')."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GitHubFileDeletionEntity",
      children: [jsx(_components.p, {
        children: "Schema for GitHub file deletion entity."
      }), jsx(_components.p, {
        children: "This entity is used to signal that a file has been removed from the repository\nand should be deleted from the destination."
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
              children: "file_path"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Path of the deleted file within the repository"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "repo_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the repository containing the deleted file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "repo_owner"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Owner of the repository"
            })]
          })]
        })]
      })]
    }), "\n", "\n", jsx(_components.h2, {
      children: "Setting up a GitHub Personal Access Token for Airweave"
    }), "\n", jsx(_components.p, {
      children: "To connect your GitHub repositories to Airweave, you'll need to create a Personal Access Token (PAT) with the appropriate permissions. This guide walks you through the process of creating and configuring a fine-grained token for use with Airweave."
    }), "\n", jsx(_components.h3, {
      children: "Step 1: Access Developer Settings in GitHub"
    }), "\n", jsx(_components.p, {
      children: 'Navigate to your GitHub account settings by clicking on your profile picture in the top right corner, then select "Settings". From there, scroll down to find and click on "Developer settings" in the left sidebar.'
    }), "\n", jsx("img", {
      src: "find-developer-settings.png",
      alt: "Finding Developer Settings in GitHub",
      width: "600"
    }), "\n", jsx(_components.h3, {
      children: "Step 2: Create a New Fine-Grained Token"
    }), "\n", jsx(_components.p, {
      children: 'In the Developer settings page, select "Fine-grained tokens" from the left menu, then click on "Generate new token".'
    }), "\n", jsx("img", {
      src: "fine-grained-token.png",
      alt: "Fine-grained tokens section",
      width: "600"
    }), "\n", jsx(_components.h3, {
      children: "Step 3: Configure Your Token"
    }), "\n", jsx(_components.p, {
      children: "Fill out the token form with the following details:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Token name"
        }), ': Choose a descriptive name like "Airweave Integration"']
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Expiration"
        }), ": Select an appropriate expiration date (recommended: 1 year for production use)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Repository access"
        }), ': Choose either "All repositories" or select specific repositories you want to connect to Airweave']
      }), "\n"]
    }), "\n", jsx("img", {
      src: "create-new-token.png",
      alt: "Creating a new token",
      width: "600"
    }), "\n", jsx(_components.h3, {
      children: "Step 4: Set Required Permissions"
    }), "\n", jsx(_components.p, {
      children: "For the GitHub connector to work properly, you need to grant the following permissions:"
    }), "\n", jsx(_components.p, {
      children: 'Under "Repository permissions":'
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: 'Set "Contents" to "Read-only" - This allows Airweave to read repository files'
      }), "\n"]
    }), "\n", jsx("img", {
      src: "add-conent-to-read-rights.png",
      alt: "Setting content permissions",
      width: "600"
    }), "\n", jsx(_components.h3, {
      children: "Step 5: Generate and Save Your Token"
    }), "\n", jsx(_components.p, {
      children: 'After configuring the permissions, scroll to the bottom of the page and click "Generate token".'
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Important"
      }), ": GitHub will display your token only once. Make sure to copy and store it in a secure location, as you won't be able to view it again."]
    }), "\n", jsx(_components.h3, {
      children: "Step 6: Add Your Token to Airweave"
    }), "\n", jsx(_components.p, {
      children: "When setting up the GitHub connector in Airweave:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Authentication"
        }), ': Paste your personal access token in the "Personal Access Token" field']
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Configuration"
        }), ": Enter the repository name in the format ", jsx(_components.code, {
          children: "owner/repo"
        }), " (e.g., ", jsx(_components.code, {
          children: "airweave-ai/airweave"
        }), ') in the "Repository Name" configuration field']
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "Your GitHub repository is now connected to Airweave and ready for synchronization."
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
