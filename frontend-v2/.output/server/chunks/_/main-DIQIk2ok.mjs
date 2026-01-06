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
        alt: "Sharepoint logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Sharepoint"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "SharePoint source connector integrates with the Microsoft Graph API."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from SharePoint including sites, document libraries,\nfiles, users, and groups."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to SharePoint resources with intelligent\nerror handling and rate limiting."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/sharepoint.py",
      children: jsx(_components.p, {
        children: "Explore the Sharepoint connector implementation"
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
      title: "SharePointUserEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint user."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/user",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/user"
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
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name displayed in the address book for the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_principal_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsxs(_components.td, {
              children: ["The user principal name (UPN) of the user (e.g., ", jsx(_components.a, {
                href: "mailto:user@contoso.com",
                children: "user@contoso.com"
              }), ")."]
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mail"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The SMTP address for the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "job_title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The user's job title."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "department"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The department in which the user works."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "office_location"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The office location in the user's place of business."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mobile_phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The primary cellular telephone number for the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "business_phones"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "The telephone numbers for the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "account_enabled"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the account is enabled."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointGroupEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint group."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/group",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/group"
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
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The display name for the group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "An optional description for the group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mail"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The SMTP address for the group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mail_enabled"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the group is mail-enabled."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "security_enabled"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the group is a security group."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "group_types"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Specifies the group type (e.g., 'Unified' for Microsoft 365 groups)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "visibility"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Visibility of the group (Public, Private, HiddenMembership)."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointSiteEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint site."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/site",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/site"
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
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The full title for the site."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name/title of the site."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The descriptive text for the site."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL that displays the site in the browser."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_personal_site"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the site is a personal site."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_collection"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Details about the site's site collection."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointDriveEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint drive (document library)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/drive",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/drive"
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
              children: "User-visible description of the drive."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "drive_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of drive (documentLibrary, business, etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the drive in a browser."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the drive's owner."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "quota"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the drive's storage quota."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the site that contains this drive."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointDriveItemEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint drive item (file or folder)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/driveitem",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/driveitem"
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
              children: "User-visible description of the item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to display the item in a browser."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "file"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "File metadata if the item is a file (e.g., mimeType, hashes)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "folder"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Folder metadata if the item is a folder (e.g., childCount)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_reference"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the parent of this item (driveId, path, etc)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the site that contains this item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "drive_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the drive that contains this item."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointListEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint list."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/list",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/list"
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
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The displayable title of the list."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "list_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name of the list."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The description of the list."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the list in browser."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "list_info"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Additional list metadata (template, hidden, etc)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the site that contains this list."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointListItemEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint list item."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/listitem",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/listitem"
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
              children: "fields"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The values of the columns set on this list item (dynamic schema)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_type"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The content type of this list item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the item in browser."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "list_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the list that contains this item."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the site that contains this item."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SharePointPageEntity",
      children: [jsx(_components.p, {
        children: "Schema for a SharePoint site page."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/sitepage",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/sitepage"
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
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The title of the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "page_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name of the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The actual page content (extracted from webParts)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description or summary of the page content."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "page_layout"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The layout type of the page (article, home, etc)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the page in browser."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "publishing_state"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Publishing status of the page."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "site_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the site that contains this page."
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
