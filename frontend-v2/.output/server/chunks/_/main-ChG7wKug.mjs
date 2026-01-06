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
        alt: "Google Drive logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Google Drive"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Google Drive source connector integrates with the Google Drive API to extract files."
    }), "\n", jsx(_components.p, {
      children: "Supports both personal Google Drive (My Drive) and shared drives."
    }), "\n", jsx(_components.p, {
      children: "It supports downloading and processing files\nwhile maintaining proper organization and access permissions."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/google_drive.py",
      children: jsx(_components.p, {
        children: "Explore the Google Drive connector implementation"
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
        children: "Google Drive configuration schema."
      }), jsx(ParamField, {
        path: "include_patterns",
        type: "list[str]",
        required: false,
        default: "[]",
        children: jsx(_components.p, {
          children: "List of file/folder paths to include in synchronization. Examples: 'my_folder/*', 'my_folder/my_file.pdf'. Separate multiple patterns with commas. If empty, all files are included."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "GoogleDriveDriveEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Drive resource (shared drive)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.google.com/drive/api/v3/reference/drives",
          children: "https://developers.google.com/drive/api/v3/reference/drives"
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
              children: "kind"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: 'Identifies what kind of resource this is; typically "drive#drive".'
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "color_rgb"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The color of this shared drive as an RGB hex string."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "hidden"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the shared drive is hidden from default view."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "org_unit_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The organizational unit of this shared drive, if applicable."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GoogleDriveFileEntity",
      children: [jsx(_components.p, {
        children: "Schema for a File resource (in a user's or shared drive)."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.google.com/drive/api/v3/reference/files",
          children: "https://developers.google.com/drive/api/v3/reference/files"
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
              children: "Optional description of the file."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "starred"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the user has starred the file."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "trashed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the file is in the trash."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "explicitly_trashed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the file was explicitly trashed by the user."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parents"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "IDs of the parent folders containing this file."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owners"
            }), jsx(_components.td, {
              children: "List[Any]"
            }), jsx(_components.td, {
              children: "Owners of the file."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shared"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the file is shared."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_view_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Link for opening the file in a relevant Google editor or viewer."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "icon_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A static, far-reaching URL to the file's icon."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "md5_checksum"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "MD5 checksum for the content of the file."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GoogleDriveFileDeletionEntity",
      children: [jsx(_components.p, {
        children: "Deletion signal for a Google Drive file."
      }), jsxs(_components.p, {
        children: ["Emitted when the Drive Changes API reports a file was removed (deleted or access lost).\nThe ", jsx(_components.code, {
          children: "entity_id"
        }), " matches the original file's ID so downstream deletion can target\nthe correct parent/children."]
      }), jsx(_components.table, {
        children: jsx(_components.thead, {
          children: jsxs(_components.tr, {
            children: [jsx(_components.th, {
              children: "Field"
            }), jsx(_components.th, {
              children: "Type"
            }), jsx(_components.th, {
              children: "Description"
            })]
          })
        })
      })]
    }), "\n", "\n", jsx(_components.h2, {
      children: "Integrate Airweave with Google APIs on localhost"
    }), "\n", jsxs(_components.p, {
      children: ["This guide will walk you through connecting Google Workspace APIs to Airweave when running locally.\nGoogle provides extensive ", jsx(_components.a, {
        href: "https://developers.google.com/workspace/guides/get-started",
        children: "documentation"
      }), " on setting up your workspace.\nBelow is a streamlined process for connecting Google APIs to Airweave."]
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/create-project",
          children: "Create a Google Cloud project"
        }), " for your Google Workspace (if you don't already have one)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/enable-apis",
          children: "Enable the Google Workspace APIs"
        }), " for Gmail, Google Calendar, and Google Drive"]
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/configure-oauth-consent",
          children: "Configure Google OAuth 2.0 consent screen"
        })
      }), "\n", jsxs(_components.li, {
        children: ["Under ", jsx(_components.code, {
          children: "Audience"
        }), ", select ", jsx(_components.code, {
          children: "Make external"
        }), " and add test users"]
      }), "\n", jsxs(_components.li, {
        children: ["Under ", jsx(_components.code, {
          children: "Data Access"
        }), ", add the following scopes:"]
      }), "\n"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "https://www.googleapis.com/auth/docs\nhttps://www.googleapis.com/auth/drive.photos.readonly\nhttps://www.googleapis.com/auth/drive\nhttps://www.googleapis.com/auth/drive.readonly\nhttps://www.googleapis.com/auth/drive.metadata\nhttps://www.googleapis.com/auth/drive.metadata.readonly\nhttps://www.googleapis.com/auth/gmail.readonly\nhttps://www.googleapis.com/auth/calendar.events.public.readonly\nhttps://www.googleapis.com/auth/calendar.freebusy\nhttps://www.googleapis.com/auth/calendar.readonly\nhttps://www.googleapis.com/auth/calendar.calendars.readonly\nhttps://www.googleapis.com/auth/calendar.events.owned.readonly\nhttps://www.googleapis.com/auth/calendar.events.readonly\n"
      })
    }), "\n", jsxs(_components.ol, {
      start: "6",
      children: ["\n", jsxs(_components.li, {
        children: ["\n", jsx(_components.p, {
          children: jsx(_components.a, {
            href: "https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",
            children: "Create OAuth client ID credentials"
          })
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: ['Under "Authorized redirect URIs," click "+ Add URI" and add the Redirect URI. Use the appropriate URL for your environment:\n', jsx(_components.strong, {
            children: "Production (Airweave Cloud):"
          })]
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
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: ["Locate the client ID and client secret from your newly created OAuth client. Add these credentials to the ", jsx(_components.code, {
            children: "dev.integrations.yml"
          }), " file to enable Google API integration."]
        }), "\n"]
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
