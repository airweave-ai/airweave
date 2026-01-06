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
    h4: "h4",
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
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Callout, CodeBlocks, Step, Steps } = _components;
  if (!Callout) _missingMdxReference("Callout");
  if (!CodeBlocks) _missingMdxReference("CodeBlocks");
  if (!Step) _missingMdxReference("Step");
  if (!Steps) _missingMdxReference("Steps");
  return jsxs(Fragment, {
    children: [jsx("div", {
      style: {
        textAlign: "center",
        margin: "2rem 0"
      },
      children: jsxs("picture", {
        children: [jsx("source", {
          media: "(prefers-color-scheme: dark)",
          srcSet: "/docs/assets/images/auth-providers/composio-dark.svg"
        }), jsx("source", {
          media: "(prefers-color-scheme: light)",
          srcSet: "/docs/assets/images/auth-providers/composio-light.svg"
        }), jsx("img", {
          src: "/docs/assets/images/auth-providers/composio-light.svg",
          alt: "Composio Integration",
          style: {
            maxWidth: "400px"
          }
        })]
      })
    }), "\n", jsx(_components.h2, {
      children: "Overview"
    }), "\n", jsx(_components.p, {
      children: "Composio enables Airweave to access credentials from integrated applications. When your users connect their accounts through Composio, Airweave can automatically retrieve those credentials for data synchronization."
    }), "\n", jsx(_components.h2, {
      children: "Prerequisites"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "A Composio account with API access"
      }), "\n", jsx(_components.li, {
        children: "Your Composio API key"
      }), "\n", jsx(_components.li, {
        children: "Connected user accounts in Composio for the sources you want to sync"
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Setup Guide"
    }), "\n", jsxs(Steps, {
      children: [jsxs(Step, {
        title: "Get your Composio API Key",
        toc: true,
        children: [jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: ["Log in to your ", jsx(_components.a, {
              href: "https://platform.composio.dev",
              children: "Composio dashboard"
            }), " and navigate to your Project."]
          }), "\n", jsx(_components.li, {
            children: "Go to your Project settings."
          }), "\n", jsx(_components.li, {
            children: "Copy your API key from the Project API Keys."
          }), "\n"]
        }), jsx("video", {
          src: "./composio_api_key.mp4",
          controls: true,
          loop: true,
          autoplay: true,
          muted: true,
          playsinline: true,
          style: {
            aspectRatio: "16 / 9",
            width: "100%"
          },
          children: jsx(_components.p, {
            children: "Your browser does not support the video tag."
          })
        })]
      }), jsx(Step, {
        title: "Connect Composio to Airweave",
        toc: true,
        children: jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: ["Go to ", jsx(_components.a, {
              href: "https://app.airweave.ai/auth-providers",
              children: "Airweave Auth Providers"
            })]
          }), "\n", jsx(_components.li, {
            children: 'Click "Connect" next to Composio'
          }), "\n", jsx(_components.li, {
            children: "Enter your API key"
          }), "\n", jsx(_components.li, {
            children: "Provide a readable name for this connection"
          }), "\n", jsx(_components.li, {
            children: 'Click "Save"'
          }), "\n"]
        })
      }), jsxs(Step, {
        title: "Find your connection details",
        toc: true,
        children: [jsx(_components.p, {
          children: "To create source connections, you'll need two identifiers from Composio:"
        }), jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "auth_config_id"
            }), ": Navigate to your Auth Configs page"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "account_id"
            }), ": Click on an auth config to see its connected accounts"]
          }), "\n"]
        }), jsx(Callout, {
          type: "info",
          children: jsxs(_components.p, {
            children: [jsx(_components.strong, {
              children: "Tip"
            }), ": In Composio, one auth config can have multiple connected accounts, allowing you to manage different user connections under the same integration."]
          })
        })]
      }), jsxs(Step, {
        title: "Create Source Connections",
        toc: true,
        children: [jsx(_components.p, {
          children: "Now you can create source connections that automatically retrieve credentials from Composio:"
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'from airweave import AirweaveSDK\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\n# Create a Google Drive connection using Composio credentials\nsource_connection = client.source_connections.create(\n    name="Sales Team Google Drive",\n    short_name="google_drive",\n    authentication={\n        "provider_readable_id": "my-composio-connection-abc123",  # Your Composio auth provider id\n        "provider_config": {\n            "auth_config_id": "config_xyz789",  # From Composio dashboard\n            "account_id": "account_abc123"      # From Composio dashboard\n        }\n    }\n)\n\nprint(f"Created: {source_connection.name}")\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-typescript",
              children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst client = new AirweaveSDKClient({\n  apiKey: "YOUR_API_KEY"\n});\n\n// Create a Google Drive connection using Composio credentials\nconst sourceConnection = await client.sourceConnections.create({\n  name: "Sales Team Google Drive",\n  shortName: "google_drive",\n  authentication: {\n    providerReadableId: "my-composio-connection-abc123",  // Your Composio connection ID\n    providerConfig: {\n      authConfigId: "config_xyz789",  // From Composio dashboard\n      accountId: "account_abc123"     // From Composio dashboard\n    }\n  }\n});\n\nconsole.log(`Created: ${sourceConnection.name}`);\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: `curl -X POST 'https://app.airweave.ai/source-connections' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "name": "Sales Team Google Drive",
  "short_name": "google_drive",
  "authentication": {
    "provider_readable_id": "my-composio-connection-abc123",
    "provider_config": {
      "auth_config_id": "config_xyz789",
      "account_id": "account_abc123"
    }
  }
}'
`
            })
          }), jsxs(Callout, {
            type: "warning",
            children: [jsxs(_components.p, {
              children: [jsx(_components.strong, {
                children: "Note"
              }), ": API Validation"]
            }), jsx(_components.p, {
              children: "The API now performs validation on auth provider source connections:"
            }), jsxs(_components.ol, {
              children: ["\n", jsxs(_components.li, {
                children: [jsx(_components.strong, {
                  children: "Provider Existence"
                }), ": 404 error if the specified ", jsx(_components.code, {
                  children: "provider_readable_id"
                }), " doesn't exist"]
              }), "\n", jsxs(_components.li, {
                children: [jsx(_components.strong, {
                  children: "Source Compatibility"
                }), ": 400 error if the provider doesn't support the specified source"]
              }), "\n"]
            }), jsx(_components.p, {
              children: jsx(_components.strong, {
                children: "Example error response when provider doesn't support a source:"
              })
            }), jsx(_components.pre, {
              children: jsx(_components.code, {
                className: "language-json",
                children: `{
  "detail": "Source 'github' does not support 'composio' as an auth provider. Supported providers: []"
}
`
              })
            })]
          })]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "How It Works"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-mermaid",
        children: 'sequenceDiagram\n    participant You\n    participant Airweave\n    participant Composio\n    participant GoogleDrive as Google Drive\n\n    Note over You,GoogleDrive: Setup Phase\n    You->>Composio: Connect Google Drive\n    Composio-->>You: auth_config_id: "config_xyz789"<br/>account_id: "account_abc123"\n\n    Note over You,GoogleDrive: Create Source Connection\n    You->>Airweave: POST /source-connections\n    Note over You,Airweave: provider_readable_id: "composio-prod-abc123"<br/>auth_config_id: "config_xyz789"<br/>account_id: "account_abc123"\n\n    Note over You,GoogleDrive: Sync Data\n    You->>Airweave: Trigger sync\n    Airweave->>Composio: GET /connected_accounts\n    Note over Airweave,Composio: Filter by auth_config_id & account_id\n    Composio-->>Airweave: OAuth credentials\n    Airweave->>GoogleDrive: Sync with credentials\n    GoogleDrive-->>Airweave: Documents & files\n    Airweave-->>You: ✓ Sync complete\n'
      })
    }), "\n", jsx(_components.h2, {
      children: "Field Mappings"
    }), "\n", jsx(_components.p, {
      children: "Some sources use different field names between Airweave and Composio:"
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Airweave Field"
          }), jsx(_components.th, {
            children: "Composio Field"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "api_key"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "generic_api_key"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "google_drive"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "googledrive"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "google_calendar"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "googlecalendar"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "outlook_mail"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "outlook"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "onedrive"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "one_drive"
            })
          })]
        })]
      })]
    }), "\n", jsx(_components.p, {
      children: "These mappings are handled automatically by Airweave."
    }), "\n", jsx(_components.h2, {
      children: "Troubleshooting"
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "No matching connection found"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: ["Verify the ", jsx(_components.code, {
          children: "auth_config_id"
        }), " and ", jsx(_components.code, {
          children: "account_id"
        }), " are correct"]
      }), "\n", jsx(_components.li, {
        children: "Ensure the account is connected in Composio"
      }), "\n", jsxs(_components.li, {
        children: ["Check that the integration type matches (e.g., ", jsx(_components.code, {
          children: "google_drive"
        }), " vs ", jsx(_components.code, {
          children: "googledrive"
        }), ")"]
      }), "\n"]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "Missing required auth fields"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "The source may require additional fields not available in Composio"
      }), "\n", jsx(_components.li, {
        children: "Check the field mappings section above"
      }), "\n", jsx(_components.li, {
        children: "Contact support if a mapping is missing"
      }), "\n"]
    }), "\n", jsx(_components.h4, {
      children: jsx(_components.code, {
        children: "Authentication failed"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Verify your Composio API key is valid"
      }), "\n", jsx(_components.li, {
        children: "Check if the user's connection in Composio is still active"
      }), "\n", jsx(_components.li, {
        children: "Ensure the connected account has the necessary permissions"
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "API Reference"
    }), "\n", jsxs(_components.p, {
      children: ["For full API details, see the ", jsx(_components.a, {
        href: "/api-reference/source-connections/create-source-connections-post",
        children: "Source Connections API reference"
      }), "."]
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
