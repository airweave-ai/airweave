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
        alt: "Box logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Box"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Box source connector integrates with the Box API to extract and synchronize data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Box account and syncs folders, files, comments, users, and collaborations."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/box.py",
      children: jsx(_components.p, {
        children: "Explore the Box connector implementation"
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
        children: "Box configuration schema."
      }), jsx(ParamField, {
        path: "folder_id",
        type: "str",
        required: false,
        default: "0",
        children: jsx(_components.p, {
          children: "Specific Box folder ID to sync. Default is '0' (root folder, syncs all files). To sync a specific folder, enter its folder ID. You can find folder IDs in the Box URL when viewing a folder."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "BoxUserEntity",
      children: [jsx(_components.p, {
        children: "Schema for Box user entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.box.com/reference/resources/user/",
          children: "https://developer.box.com/reference/resources/user/"
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
              children: "login"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Login email address of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the user (active, inactive, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "job_title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Job title of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Phone number of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "address"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Address of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "language"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Language of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Timezone of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Total storage space available to the user in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_used"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Storage space used by the user in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "max_upload_size"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Maximum file size the user can upload in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "avatar_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to the user's avatar image"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BoxFolderEntity",
      children: [jsx(_components.p, {
        children: "Schema for Box folder entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.box.com/reference/resources/folder/",
          children: "https://developer.box.com/reference/resources/folder/"
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
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "size"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Size of the folder in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "path_collection"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Path of parent folders from root to this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_created_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the content in this folder was originally created"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_modified_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the content in this folder was last modified"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who created this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who last modified this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owned_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who owns this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the parent folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the parent folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the folder (active, trashed, deleted)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shared_link"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Shared link information for this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "folder_upload_email"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Email address that can be used to upload files to this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Tags associated with this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_collaborations"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether this folder has collaborations"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permissions"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Permissions the current user has on this folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Direct link to view the folder in Box"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "etag"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Entity tag for versioning"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sequence_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Sequence ID for the most recent user event"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BoxFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for Box file entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.box.com/reference/resources/file/",
          children: "https://developer.box.com/reference/resources/file/"
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
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_folder_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the parent folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_folder_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the parent folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "path_collection"
            }), jsx(_components.td, {
              children: "List[Dict]"
            }), jsx(_components.td, {
              children: "Path of parent folders from root to this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sha1"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "SHA1 hash of the file contents"
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
              children: "version_number"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Version number of the file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "comment_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of comments on this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_created_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the content of this file was originally created"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_modified_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the content of this file was last modified"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who created this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who last modified this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owned_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who owns this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the file (active, trashed, deleted)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shared_link"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Shared link information for this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Tags associated with this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_collaborations"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether this file has collaborations"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permissions"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Permissions the current user has on this file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "lock"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Lock information if the file is locked"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Direct link to view the file in Box"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "etag"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Entity tag for versioning"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sequence_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Sequence ID for the most recent user event"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BoxCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Box comment entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.box.com/reference/resources/comment/",
          children: "https://developer.box.com/reference/resources/comment/"
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
              children: "file_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the file this comment is on"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "file_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "message"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Content of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Dict"
            }), jsx(_components.td, {
              children: "User who created this comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_reply_comment"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this comment is a reply to another comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tagged_message"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Tagged version of the message with user mentions"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "BoxCollaborationEntity",
      children: [jsx(_components.p, {
        children: "Schema for Box collaboration entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.box.com/reference/resources/collaboration/",
          children: "https://developer.box.com/reference/resources/collaboration/"
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
              children: "role"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Role of the collaborator (editor, viewer, previewer, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "accessible_by"
            }), jsx(_components.td, {
              children: "Dict"
            }), jsx(_components.td, {
              children: "User or group that this collaboration applies to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item"
            }), jsx(_components.td, {
              children: "Dict"
            }), jsx(_components.td, {
              children: "File or folder that is being collaborated on"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the item being collaborated on"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Type of the item (file or folder)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "item_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the item being collaborated on"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Status of the collaboration (accepted, pending, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "User who created this collaboration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "expires_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When this collaboration expires"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_access_only"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether this is an access-only collaboration"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "invite_email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Email address invited to collaborate"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "acknowledged_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the collaboration was acknowledged"
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
