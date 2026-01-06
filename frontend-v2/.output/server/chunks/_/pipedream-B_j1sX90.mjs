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
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Accordion, AccordionGroup, Callout, CodeBlocks, Step, Steps } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
  if (!AccordionGroup) _missingMdxReference("AccordionGroup");
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
      children: jsx("img", {
        src: "/docs/assets/images/auth-providers/pipedream.jpeg",
        alt: "Pipedream Integration",
        style: {
          maxWidth: "300px",
          borderRadius: "8px"
        }
      })
    }), "\n", jsx(_components.h2, {
      children: "Overview"
    }), "\n", jsx(_components.p, {
      children: "Pipedream enables workflow automation with 2,000+ integrated apps. Airweave can leverage your existing Pipedream connections to sync data without requiring users to authenticate again."
    }), "\n", jsx(_components.p, {
      children: "This integration involves two separate OAuth clients:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Pipedream OAuth client"
        }), ": Allows Airweave to access Pipedream's API"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Source app OAuth clients"
        }), ": Custom OAuth clients you create for each source app (Notion, Google Drive, etc.)"]
      }), "\n"]
    }), "\n", jsx(Callout, {
      type: "warning",
      children: jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Important"
        }), ": Pipedream only exposes credentials for accounts created with your own custom OAuth clients. Default Pipedream OAuth connections use the Proxy API."]
      })
    }), "\n", jsx(_components.h2, {
      children: "Prerequisites"
    }), "\n", jsx(_components.h3, {
      children: "For Pipedream API access:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "A Pipedream account with API access"
      }), "\n", jsx(_components.li, {
        children: "Pipedream OAuth client credentials (for Airweave to Pipedream authentication)"
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "For source app access:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Custom OAuth clients created in each source app (Notion, Google Drive, etc.)"
      }), "\n", jsx(_components.li, {
        children: "Source app accounts connected to Pipedream using your custom OAuth clients"
      }), "\n", jsx(_components.li, {
        children: "Not accounts connected using Pipedream's default OAuth implementations"
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Setup Guide"
    }), "\n", jsxs(Steps, {
      children: [jsxs(Step, {
        title: "Set up Pipedream OAuth client",
        toc: true,
        children: [jsx(_components.p, {
          children: "First, configure the OAuth client that allows Airweave to access Pipedream's API:"
        }), jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: ["\n", jsxs(_components.p, {
              children: ["Log in to ", jsx(_components.a, {
                href: "https://pipedream.com",
                children: "Pipedream"
              })]
            }), "\n"]
          }), "\n", jsxs(_components.li, {
            children: ["\n", jsx(_components.p, {
              children: "Navigate to your Project Settings"
            }), "\n"]
          }), "\n", jsxs(_components.li, {
            children: ["\n", jsx(_components.p, {
              children: "Create a new OAuth client for Airweave integration"
            }), "\n"]
          }), "\n", jsxs(_components.li, {
            children: ["\n", jsx(_components.p, {
              children: "Configure redirect URIs if required"
            }), "\n"]
          }), "\n", jsxs(_components.li, {
            children: ["\n", jsxs(_components.p, {
              children: ["Save your ", jsx(_components.code, {
                children: "client_id"
              }), " and ", jsx(_components.code, {
                children: "client_secret"
              })]
            }), "\n", jsx("video", {
              src: "./create_pipedream_api_key.mp4",
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
            }), "\n"]
          }), "\n"]
        }), jsx(Callout, {
          type: "info",
          children: jsxs(_components.p, {
            children: [jsx(_components.strong, {
              children: "Purpose"
            }), ": This OAuth client enables Airweave to authenticate with Pipedream's API to retrieve your connected account credentials."]
          })
        })]
      }), jsx(Step, {
        title: "Connect Pipedream to Airweave",
        toc: true,
        children: jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: ["Go to ", jsx(_components.a, {
              href: "https://app.airweave.ai/auth-providers",
              children: "Airweave Auth Providers"
            })]
          }), "\n", jsx(_components.li, {
            children: 'Click "Connect" next to Pipedream'
          }), "\n", jsxs(_components.li, {
            children: ["Enter your Pipedream OAuth client credentials:", "\n", jsxs(_components.ul, {
              children: ["\n", jsxs(_components.li, {
                children: [jsx(_components.code, {
                  children: "client_id"
                }), " (from step 1)"]
              }), "\n", jsxs(_components.li, {
                children: [jsx(_components.code, {
                  children: "client_secret"
                }), " (from step 1)"]
              }), "\n"]
            }), "\n"]
          }), "\n", jsx(_components.li, {
            children: "Provide a readable name for this connection"
          }), "\n", jsx(_components.li, {
            children: 'Click "Save"'
          }), "\n"]
        })
      }), jsxs(Step, {
        title: "Create custom OAuth clients for source apps",
        toc: true,
        children: [jsx(_components.p, {
          children: "For each source app you want to sync (Notion, Google Drive, etc.), you must create custom OAuth clients:"
        }), jsxs(AccordionGroup, {
          children: [jsx(Accordion, {
            title: "For Notion",
            children: jsxs(_components.ol, {
              children: ["\n", jsxs(_components.li, {
                children: ["Go to ", jsx(_components.a, {
                  href: "https://developers.notion.com",
                  children: "Notion Developers"
                })]
              }), "\n", jsx(_components.li, {
                children: "Create a new integration"
              }), "\n", jsx(_components.li, {
                children: "Configure OAuth settings with your redirect URIs"
              }), "\n", jsxs(_components.li, {
                children: ["Save the ", jsx(_components.code, {
                  children: "client_id"
                }), " and ", jsx(_components.code, {
                  children: "client_secret"
                })]
              }), "\n"]
            })
          }), jsx(Accordion, {
            title: "For Other Apps:",
            children: jsx(_components.p, {
              children: "Follow similar steps for Google Drive, GitHub, or other source integrations."
            })
          })]
        }), jsx(Callout, {
          type: "warning",
          children: jsxs(_components.p, {
            children: [jsx(_components.strong, {
              children: "Important"
            }), ": You must use these custom OAuth clients when connecting accounts in Pipedream. Do not use Pipedream's built-in OAuth options."]
          })
        })]
      }), jsx(Step, {
        title: "Connect source apps in Pipedream using custom OAuth",
        toc: true,
        children: jsxs(_components.ol, {
          children: ["\n", jsx(_components.li, {
            children: "In Pipedream, go to your project's connections"
          }), "\n", jsxs(_components.li, {
            children: ["For each source app (Notion, Google Drive, etc.):", "\n", jsxs(_components.ul, {
              children: ["\n", jsx(_components.li, {
                children: 'Choose "Custom OAuth" option'
              }), "\n", jsx(_components.li, {
                children: "Enter your custom OAuth client credentials from Step 3"
              }), "\n", jsx(_components.li, {
                children: "Complete the OAuth flow to connect your account"
              }), "\n"]
            }), "\n"]
          }), "\n", jsxs(_components.li, {
            children: ["Note the ", jsx(_components.code, {
              children: "account_id"
            }), " for each connection (format: ", jsx(_components.code, {
              children: "apn_xxxxx"
            }), ")"]
          }), "\n"]
        })
      }), jsxs(Step, {
        title: "Find your connection details",
        toc: true,
        children: [jsx(_components.p, {
          children: "To create source connections, you'll need these identifiers:"
        }), jsxs(_components.ol, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "project_id"
            }), ": Found in the URL when viewing your project (e.g., ", jsx(_components.code, {
              children: "proj_JPsD74a"
            }), ")"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "account_id"
            }), ": Retrieved via Pipedream UI or API"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "external_user_id"
            }), ": Retrieved via Pipedream UI or API"]
          }), "\n"]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-bash",
            children: 'curl -X GET "https://api.pipedream.com/v1/connect/{project_id}/accounts?include_credentials=true" \\\n  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"\n'
          })
        }), jsxs(_components.p, {
          children: ["The response will include account IDs like ", jsx(_components.code, {
            children: "apn_gyha5Ky"
          }), "."]
        })]
      }), jsxs(Step, {
        title: "Create Source Connections",
        toc: true,
        children: [jsx(_components.p, {
          children: "Create source connections that automatically retrieve credentials from Pipedream:"
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-python",
              children: 'from airweave import AirweaveSDK\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\n# Create a Notion connection using Pipedream credentials\nsource_connection = client.source_connections.create(\n    name="Company Notion Workspace",\n    short_name="notion",\n    authentication={\n        "provider_readable_id": "my-pipedream-connection-xyz789",  # Your Pipedream connection ID\n        "provider_config": {\n            "project_id": "proj_JPsD74a",      # From Pipedream\n            "account_id": "apn_gyha5Ky",       # From Pipedream API\n            "external_user_id": "user123",     # Required: unique user identifier\n            "environment": "production",        # Optional, defaults to "production"\n        }\n    }\n)\n\nprint(f"Created: {source_connection.name}")\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-typescript",
              children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst client = new AirweaveSDKClient({\n  apiKey: "YOUR_API_KEY"\n});\n\n// Create a Notion connection using Pipedream credentials\nconst sourceConnection = await client.sourceConnections.create({\n  name: "Company Notion Workspace",\n  shortName: "notion",\n  authentication: {\n    providerReadableId: "my-pipedream-connection-xyz789",  // Your Pipedream connection ID\n    providerConfig: {\n      project_id: "proj_JPsD74a",      // From Pipedream\n      account_id: "apn_gyha5Ky",       // From Pipedream API\n      external_user_id: "user123",     // Required: unique user identifier\n      environment: "production",      // Optional, defaults to "production"\n    }\n  }\n});\n\nconsole.log(`Created: ${sourceConnection.name}`);\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: `curl -X POST 'https://app.airweave.ai/source-connections' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "name": "Company Notion Workspace",
  "short_name": "notion",
  "authentication": {
    "provider_readable_id": "my-pipedream-connection-xyz789",
    "provider_config": {
      "project_id": "proj_JPsD74a",
      "account_id": "apn_gyha5Ky",
      "environment": "production",
      "external_user_id": "user123"
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
  "detail": "Source 'github' does not support 'pipedream' as an auth provider. Supported providers: []"
}
`
              })
            })]
          })]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "How It Works"
    }), "\n", jsx(_components.p, {
      children: "The integration uses two distinct OAuth flows:"
    }), "\n", jsx(_components.h3, {
      children: "OAuth flow overview"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Airweave to Pipedream"
        }), ": Uses your Pipedream OAuth client for API access"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Pipedream to source apps"
        }), ": Uses your custom OAuth clients for each source app"]
      }), "\n"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-mermaid",
        children: `sequenceDiagram
    participant You
    participant Airweave
    participant Pipedream
    participant Notion

    Note over You,Notion: Setup Phase (Two OAuth clients)
    You->>Notion: Create custom OAuth client
    Note over You,Notion: client_id: "notion_abc123"<br/>client_secret: "notion_secret"
    You->>Pipedream: Connect Notion with your OAuth client
    Note over You,Pipedream: Uses notion_abc123, not Pipedream's default
    Pipedream-->>You: project_id: "proj_JPsD74a"<br/>account_id: "apn_gyha5Ky"

    Note over You,Notion: Configure Airweave
    You->>Airweave: Configure Pipedream auth provider
    Note over You,Airweave: Uses your Pipedream OAuth client
    You->>Airweave: POST /source-connections
    Note over You,Airweave: provider_readable_id: "pipedream-prod-xyz789"<br/>project_id: "proj_JPsD74a"<br/>account_id: "apn_gyha5Ky"

    Note over You,Notion: Sync data (Runtime)
    You->>Airweave: Trigger sync
    Airweave->>Pipedream: POST /oauth/token
    Note over Airweave,Pipedream: Uses your Pipedream OAuth client
    Pipedream-->>Airweave: Access token (1hr expiry)
    Airweave->>Pipedream: GET /connect/proj_JPsD74a/accounts/apn_gyha5Ky
    Note over Airweave,Pipedream: include_credentials=true
    Pipedream-->>Airweave: Notion OAuth credentials
    Note over Pipedream,Airweave: Returns your custom OAuth tokens
    Airweave->>Notion: Sync with credentials
    Notion-->>Airweave: Pages & databases
    Airweave-->>You: ✓ Sync complete
`
      })
    }), "\n", jsx(_components.h2, {
      children: "Field Mappings"
    }), "\n", jsx(_components.p, {
      children: "Pipedream uses different field names for some credentials:"
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Airweave Field"
          }), jsx(_components.th, {
            children: "Pipedream Field"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "access_token"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "oauth_access_token"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "refresh_token"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "oauth_refresh_token"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "client_id"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "oauth_client_id"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "client_secret"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "oauth_client_secret"
            })
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: jsx(_components.code, {
              children: "api_key"
            })
          }), jsx(_components.td, {
            children: jsx(_components.code, {
              children: "api_key"
            })
          })]
        })]
      })]
    }), "\n", jsx(_components.p, {
      children: "These mappings are handled automatically."
    }), "\n", jsx(_components.h2, {
      children: "Token Management"
    }), "\n", jsx(_components.p, {
      children: "Pipedream OAuth tokens have specific characteristics:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Expiry"
        }), ": Access tokens expire after 3600 seconds (1 hour)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Auto-refresh"
        }), ": Airweave refreshes tokens 5 minutes before expiry"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Concurrency"
        }), ": Token refresh is thread-safe with async locks"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Grant Type"
        }), ": Uses ", jsx(_components.code, {
          children: "client_credentials"
        }), " flow"]
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Proxy Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["When you connect accounts using Pipedream's default OAuth clients, credentials aren't directly exposed for security reasons. Instead, Airweave automatically routes API requests through ", jsx(_components.a, {
        href: "https://pipedream.com/docs/connect/api-proxy",
        children: "Pipedream's proxy endpoint"
      }), ", where the actual credentials are injected server-side. This happens transparently - sources continue using the same HTTP client interface whether they're accessing credentials directly (custom OAuth) or through the proxy (default OAuth). The system automatically detects which mode to use based on the OAuth client type, ensuring your data syncs work seamlessly regardless of how the account was connected in Pipedream."]
    }), "\n", jsx(_components.h2, {
      children: "Troubleshooting"
    }), "\n", jsx(_components.h3, {
      children: jsx(_components.code, {
        children: "Credentials not available"
      })
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "Detail: Credentials not available. Pipedream only exposes credentials for\naccounts created with custom OAuth clients, not default Pipedream OAuth.\n"
      })
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Root cause"
      }), ": The account was connected using Pipedream's built-in OAuth client instead of your custom OAuth client."]
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Solution"
      }), ":"]
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "Disconnect the account in Pipedream"
      }), "\n", jsx(_components.li, {
        children: 'Reconnect using "Custom OAuth" option with your own OAuth client credentials'
      }), "\n", jsx(_components.li, {
        children: "Ensure you're using the OAuth client you created in the source app (e.g., Notion Developer Portal)"
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: jsx(_components.code, {
        children: "Account app mismatch"
      })
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "Detail: Account apn_xxx is not for app 'notion'\n"
      })
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Solution"
      }), ": Verify the ", jsx(_components.code, {
        children: "account_id"
      }), " corresponds to the correct integration type and was created with the right custom OAuth client."]
    }), "\n", jsxs(_components.h3, {
      children: [jsx(_components.code, {
        children: "Failed to refresh token"
      }), " (Airweave to Pipedream)"]
    }), "\n", jsx(_components.p, {
      children: "This affects the connection between Airweave and Pipedream's API:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Check if your Pipedream OAuth client credentials are valid"
      }), "\n", jsx(_components.li, {
        children: "Ensure your Pipedream OAuth client is active"
      }), "\n", jsx(_components.li, {
        children: "Verify network connectivity to Pipedream API"
      }), "\n"]
    }), "\n", jsxs(_components.h3, {
      children: [jsx(_components.code, {
        children: "Failed to refresh token"
      }), " (Source App Authentication)"]
    }), "\n", jsx(_components.p, {
      children: "This affects the source app tokens retrieved from Pipedream:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Verify your source app OAuth client (e.g., Notion, Google Drive) is still active"
      }), "\n", jsx(_components.li, {
        children: "Check if the source app tokens have been revoked"
      }), "\n", jsx(_components.li, {
        children: "Ensure the source app OAuth client has required permissions"
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: jsx(_components.code, {
        children: "Missing required auth fields"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "The integration may require fields not provided by your custom OAuth implementation"
      }), "\n", jsx(_components.li, {
        children: "Check the field mappings table above"
      }), "\n", jsx(_components.li, {
        children: "Verify the source app OAuth client has all required scopes"
      }), "\n", jsx(_components.li, {
        children: "Ensure your custom OAuth client configuration matches the source app's requirements"
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "API Reference"
    }), "\n", jsx(_components.h3, {
      children: "Create source connection"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-python",
          children: 'from airweave import AirweaveSDK\n\nclient = AirweaveSDK(api_key="YOUR_API_KEY")\n\nsource_connection = client.source_connections.create(\n    name="Team Notion",\n    short_name="notion",\n    provider_readable_id="pipedream-connection-id",\n    provider_config={\n        "project_id": "proj_JPsD74a",\n        "account_id": "apn_gyha5Ky",\n        "external_user_id": "user123",\n        "environment": "production"         # Optional, defaults to "production"\n    }\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-typescript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst client = new AirweaveSDKClient({\n  apiKey: "YOUR_API_KEY"\n});\n\nconst sourceConnection = await client.sourceConnections.create({\n  name: "Team Notion",\n  shortName: "notion",\n  providerReadableId: "pipedream-connection-id",\n  providerConfig: {\n    projectId: "proj_JPsD74a",\n    accountId: "apn_gyha5Ky",\n    externalUserId: "user123",\n    environment: "production"      // Optional, defaults to "production"\n  }\n});\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST 'https://app.airweave.ai/source-connections' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "name": "Team Notion",
  "short_name": "notion",
  "provider_readable_id": "pipedream-connection-id",
  "provider_config": {
    "project_id": "proj_JPsD74a",
    "account_id": "apn_gyha5Ky",
    "external_user_id": "user123",
    "environment": "production"
  }
}'
`
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Limitations"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Dual OAuth setup required"
          }), ": You need to create and manage two separate OAuth clients:"]
        }), "\n", jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: "One for Pipedream API access (Airweave to Pipedream)"
          }), "\n", jsx(_components.li, {
            children: "One for each source app (Pipedream to Notion/Asana/etc.)"
          }), "\n"]
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Custom OAuth clients only"
          }), ":"]
        }), "\n", jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: "Source app connections must use your own OAuth clients"
          }), "\n", jsx(_components.li, {
            children: "Pipedream's built-in OAuth implementations are not supported"
          }), "\n", jsx(_components.li, {
            children: "Cannot reuse existing accounts connected via Pipedream's default OAuth"
          }), "\n"]
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Token management complexity"
          }), ":"]
        }), "\n", jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: "Pipedream API tokens expire hourly, requiring automatic refresh"
          }), "\n", jsx(_components.li, {
            children: "Source app tokens managed separately through Pipedream"
          }), "\n", jsx(_components.li, {
            children: "Multiple token refresh flows to maintain"
          }), "\n"]
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "API rate limits"
          }), ": Subject to both Pipedream's API limits and source app limits"]
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Credential access"
          }), ": Only available with ", jsx(_components.code, {
            children: "include_credentials=true"
          }), " parameter and proper OAuth client setup"]
        }), "\n"]
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Next Steps"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "/sources",
          children: "Browse available sources"
        })
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "/quickstart",
          children: "Set up your first sync"
        })
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "/concepts#workflows",
          children: "Learn about workflow automation"
        })
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
