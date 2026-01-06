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
    pre: "pre",
    strong: "strong",
    table: "table",
    tbody: "tbody",
    td: "td",
    th: "th",
    thead: "thead",
    tr: "tr",
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
        alt: "Dropbox logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Dropbox"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Dropbox source connector integrates with the Dropbox API to extract and synchronize files."
    }), "\n", jsx(_components.p, {
      children: "Connects to folder structures from your Dropbox account."
    }), "\n", jsx(_components.p, {
      children: "It supports downloading and processing files."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/dropbox.py",
      children: jsx(_components.p, {
        children: "Explore the Dropbox connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses ", jsx(_components.strong, {
        children: "OAuth 2.0 with custom credentials"
      }), ". You need to provide your OAuth application's Client ID and Client Secret, then complete the OAuth consent flow."]
    }), "\n", jsx(Card, {
      title: "OAuth Setup Required",
      className: "auth-setup-card",
      style: {
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: jsxs(_components.ol, {
        children: ["\n", jsx(_components.li, {
          children: "Create an OAuth application in your provider's developer console"
        }), "\n", jsx(_components.li, {
          children: "Enter your Client ID and Client Secret when configuring the connection"
        }), "\n", jsx(_components.li, {
          children: "Complete the OAuth consent flow"
        }), "\n"]
      })
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "This connector does not have any additional configuration options."
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "DropboxAccountEntity",
      children: [jsx(_components.p, {
        children: "Schema for Dropbox account-level entities based on the Dropbox API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://www.dropbox.com/developers/documentation/http/documentation#users-get_current_account",
          children: "https://www.dropbox.com/developers/documentation/http/documentation#users-get_current_account"
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
              children: "abbreviated_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Abbreviated form of the person's name (typically initials)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "familiar_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Locale-dependent name (usually given name in US)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "given_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Also known as first name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "surname"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Also known as last name or family name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The user's email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email_verified"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user has verified their email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "disabled"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user has been disabled"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "account_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of account (basic, pro, business, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_teammate"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this user is a teammate of the current user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_paired"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user has both personal and work accounts linked"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_member_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The user's unique team member ID (if part of a team)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "locale"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The language that the user specified (IETF language tag)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "country"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The user's two-letter country code (ISO 3166-1)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "profile_photo_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL for the profile photo"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "referral_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The user's referral link"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_used"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The user's total space usage in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "space_allocated"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The user's total space allocation in bytes"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team_info"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Information about the team if user is a member"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "root_info"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Information about the user's root namespace"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "DropboxFolderEntity",
      children: [jsx(_components.p, {
        children: "Schema for Dropbox folder entities matching the Dropbox API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder",
          children: "https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder"
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
              children: "path_lower"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Lowercase full path starting with slash"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "path_display"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Display path with proper casing"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sharing_info"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Sharing information for the folder"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "read_only"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the folder is read-only"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "traverse_only"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the folder can only be traversed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "no_access"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the folder cannot be accessed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "property_groups"
            }), jsx(_components.td, {
              children: "Optional[List[Dict]]"
            }), jsx(_components.td, {
              children: "Custom properties and tags"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "DropboxFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for Dropbox file entities matching the Dropbox API."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder",
          children: "https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder"
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
              children: "path_lower"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Lowercase full path in Dropbox"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "path_display"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Display path with proper casing"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "rev"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Unique identifier for the file revision"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "client_modified"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When file was modified by client"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "server_modified"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When file was modified on server"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_downloadable"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether file can be downloaded directly"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_hash"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Dropbox content hash for integrity checks"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sharing_info"
            }), jsx(_components.td, {
              children: "Optional[Dict]"
            }), jsx(_components.td, {
              children: "Sharing information for the file"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_explicit_shared_members"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether file has explicit shared members"
            })]
          })]
        })]
      })]
    }), "\n", "\n", jsx(_components.h2, {
      children: "Integrate Airweave with Dropbox APIs on localhost"
    }), "\n", jsx(_components.p, {
      children: "Airweave will access Dropbox on behalf of your users. You'll need to have each"
    }), "\n", jsxs(_components.p, {
      children: ["Dropbox provides ", jsx(_components.a, {
        href: "https://developers.dropbox.com/oauth-guide",
        children: "documentation"
      }), " on how to implement OAuth 2.0.\nThis guide will walk you through connecting Dropbox APIs to Airweave when running locally."]
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: ["Go ", jsx(_components.a, {
            href: "https://www.dropbox.com/developers/apps/create",
            children: "here"
          }), ' to create the "Airweave integration" application']
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: ["Under ", jsx(_components.code, {
            children: "Settings"
          }), ", add the Redirect URI. Use the appropriate URL for your environment:"]
        }), "\n", jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Production (Airweave Cloud):"
          })
        }), "\n", jsx(_components.pre, {
          children: jsx(_components.code, {
            children: "https://api.airweave.ai/source-connections/callback\n"
          })
        }), "\n", jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Local:"
          })
        }), "\n", jsx(_components.pre, {
          children: jsx(_components.code, {
            children: "http://localhost:8001/source-connections/callback\n"
          })
        }), "\n"]
      }), "\n"]
    }), "\n", jsxs(_components.p, {
      children: ["3.Under ", jsx(_components.code, {
        children: "Permissions"
      }), ", select the following scopes:"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "account_info.read\nfiles.metadata.read\nfiles.content.read\nprofile\nemail\n"
      })
    }), "\n", jsxs(_components.ol, {
      start: "4",
      children: ["\n", jsxs(_components.li, {
        children: ["Locate the ", jsx(_components.code, {
          children: "App key"
        }), " and ", jsx(_components.code, {
          children: "App secret"
        }), " under ", jsx(_components.code, {
          children: "Settings"
        }), ". Add these credentials to the ", jsx(_components.code, {
          children: "dev.integrations.yml"
        }), " file to enable Dropbox API integration."]
      }), "\n"]
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
