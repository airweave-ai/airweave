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
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { CodeBlocks, Note } = _components;
  if (!CodeBlocks) _missingMdxReference("CodeBlocks");
  if (!Note) _missingMdxReference("Note");
  return jsxs(Fragment, {
    children: [jsx(_components.h2, {
      children: "Overview"
    }), "\n", jsx(_components.p, {
      children: "Direct OAuth allows you to create source connections using the standard OAuth 2.0 browser flow. This method provides a seamless user experience where users authenticate directly through their service provider's consent screen, without needing to manage tokens manually."
    }), "\n", jsx(_components.p, {
      children: "Airweave supports two main approaches for Direct OAuth:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "URL-based OAuth"
        }), ": Users authenticate through Airweave's hosted OAuth flow"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "BYOC (Bring Your Own Credentials)"
        }), ": Use your own OAuth application credentials"]
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Supported Connectors"
    }), "\n", jsx(_components.p, {
      children: "Direct OAuth is supported by most Airweave connectors. Some connectors require you to provide your own OAuth application credentials (BYOC), while others can use Airweave's hosted OAuth flow."
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Connectors requiring BYOC:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Dropbox, Gmail, Google Calendar, Google Drive"
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Connectors using Direct Authentication only:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Bitbucket, GitHub, PostgreSQL, Stripe, CTTI"
      }), "\n"]
    }), "\n", jsx(Note, {
      children: jsx(_components.p, {
        children: "Most connectors also support authentication through external providers like Composio and Pipedream."
      })
    }), "\n", jsx(_components.h2, {
      children: "URL-based OAuth Flow"
    }), "\n", jsx(_components.p, {
      children: "The URL-based OAuth flow is the simplest way to connect sources. Users are redirected to Airweave's hosted OAuth flow, which handles the entire authentication process."
    }), "\n", jsx("video", {
      src: "./direct_oauth_notion.mp4",
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
    }), "\n", jsx(_components.h3, {
      children: "How it works"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Initiate Connection"
        }), ": Create a source connection using the URL-based authentication method"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "User Consent"
        }), ": Users are redirected to the service provider's consent screen"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Token Exchange"
        }), ": Airweave exchanges the authorization code for access and refresh tokens"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Data Sync"
        }), ": The connection is established and data synchronization begins"]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Creating a URL-based OAuth connection"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-Python",
          children: 'from airweave import AirweaveSDK\nfrom airweave.types import OAuthBrowserAuthentication\n\nairweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")\n\n# Create source connection - returns pending connection with auth_url\nsource_connection = airweave.source_connections.create(\n    name="Notion connection",\n    short_name="notion",\n    readable_collection_id="my-collection-id",\n    authentication=OAuthBrowserAuthentication(\n        redirect_uri="https://your-app.com/callback"\n    ),\n    sync_immediately=False  # OAuth browser flows cannot sync immediately\n)\n\n# Connection is now in pending state - redirect user to auth_url\nprint(f"Redirect user to: {source_connection.auth.auth_url}")\nprint(f"Connection status: {source_connection.status}")  # "pending"\nprint(f"Authenticated: {source_connection.auth.authenticated}")  # False\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});\n\n// Create source connection - returns pending connection with auth_url\nconst sourceConnection = await airweave.sourceConnections.create({\n    name: "Notion connection",\n    shortName: "notion",\n    readableCollectionId: "my-collection-id",\n    authentication: {\n        redirect_uri: "https://your-app.com/callback"\n    },\n    syncImmediately: false  // OAuth browser flows cannot sync immediately\n});\n\n// Connection is now in pending state - redirect user to auth_url\nconsole.log(`Redirect user to: ${sourceConnection.auth.auth_url}`);\nconsole.log(`Connection status: ${sourceConnection.status}`);  // "pending"\nconsole.log(`Authenticated: ${sourceConnection.auth.authenticated}`);  // false\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST https://api.airweave.ai/source-connections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "Notion connection",
  "short_name": "notion",
  "readable_collection_id": "my-collection-id",
  "authentication": {
    "redirect_uri": "https://your-app.com/callback"
  },
  "sync_immediately": false
}'

# Response includes:
# {
#   "id": "connection-id",
#   "status": "pending",
#   "auth": {
#     "authenticated": false,
#     "auth_url": "https://api.airweave.ai/oauth/proxy/...",
#     "auth_url_expires": "2024-01-01T12:00:00Z"
#   }
# }
`
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Handling the OAuth callback"
    }), "\n", jsx(_components.p, {
      children: "When using URL-based OAuth, you'll receive an authorization URL that you need to redirect users to. After they complete the OAuth flow, they'll be redirected back to your specified callback URL with the necessary parameters."
    }), "\n", jsx(Note, {
      children: jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Important"
        }), ": OAuth browser flows (both standard and BYOC) cannot use ", jsx(_components.code, {
          children: "sync_immediately=true"
        }), ". The sync will automatically start after the user completes the OAuth authentication flow. Setting ", jsx(_components.code, {
          children: "sync_immediately=true"
        }), " will result in a validation error."]
      })
    }), "\n", jsx(_components.h3, {
      children: "Redirect URI basics"
    }), "\n", jsxs(_components.p, {
      children: ["The ", jsx(_components.code, {
        children: "redirect_uri"
      }), " is the URL where the user is sent after granting consent with the provider. It must exactly match an allowed redirect/callback URL configured for the OAuth app. Use it when you want users to return to your application after authentication (typical for hosted OAuth). For BYOC, configure the provider to allow Airweave's callback (", jsx(_components.code, {
        children: "https://api.airweave.ai/oauth/callback"
      }), ") and optionally set ", jsx(_components.code, {
        children: "redirect_uri"
      }), " so Airweave can forward the user back to your app after the token exchange."]
    }), "\n", jsx(_components.h2, {
      children: "BYOC (Bring Your Own Credentials)"
    }), "\n", jsx(_components.p, {
      children: "BYOC allows you to use your own OAuth application credentials instead of Airweave's hosted OAuth flow. This gives you more control over the authentication process and branding."
    }), "\n", jsx(_components.h3, {
      children: "Benefits of BYOC"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Custom Branding"
        }), ": Use your own OAuth application with your branding"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Enhanced Security"
        }), ": Control your own OAuth application settings"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Compliance"
        }), ": Meet specific compliance requirements for your organization"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Rate Limits"
        }), ": Use your own rate limits instead of shared ones"]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Setting up BYOC"
    }), "\n", jsx(_components.p, {
      children: "To use BYOC, you'll need to:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Create OAuth Application"
        }), ": Set up an OAuth application with the service provider"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Configure Redirect URI"
        }), ": Add Airweave's callback URL to your OAuth application"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Provide Credentials"
        }), ": Use your client ID and client secret in the connection"]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "How BYOC Detection Works"
    }), "\n", jsxs(_components.p, {
      children: ["BYOC (Bring Your Own Credentials) is automatically detected when you provide both ", jsx(_components.code, {
        children: "client_id"
      }), " and ", jsx(_components.code, {
        children: "client_secret"
      }), " in the ", jsx(_components.code, {
        children: "OAuthBrowserAuthentication"
      }), " object. If you provide only one of these fields, the API will return a validation error."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "BYOC Detection Logic:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: ["✅ Both ", jsx(_components.code, {
          children: "client_id"
        }), " AND ", jsx(_components.code, {
          children: "client_secret"
        }), " provided → BYOC mode"]
      }), "\n", jsxs(_components.li, {
        children: ["✅ Neither ", jsx(_components.code, {
          children: "client_id"
        }), " nor ", jsx(_components.code, {
          children: "client_secret"
        }), " provided → Standard OAuth browser flow"]
      }), "\n", jsxs(_components.li, {
        children: ["❌ Only ", jsx(_components.code, {
          children: "client_id"
        }), " OR only ", jsx(_components.code, {
          children: "client_secret"
        }), " provided → Validation error"]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Creating a BYOC connection"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-Python",
          children: 'from airweave import AirweaveSDK\nfrom airweave.types import OAuthBrowserAuthentication\n\nairweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")\n\nsource_connection = airweave.source_connections.create(\n    name="Notion connection (BYOC)",\n    short_name="notion",\n    readable_collection_id="my-collection-id",\n    authentication=OAuthBrowserAuthentication(\n        client_id="YOUR_CLIENT_ID",\n        client_secret="YOUR_CLIENT_SECRET",\n        redirect_uri="https://your-app.com/callback"\n    ),\n    sync_immediately=False  # BYOC flows cannot sync immediately\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});\n\nconst sourceConnection = await airweave.sourceConnections.create({\n    name: "Notion connection (BYOC)",\n    shortName: "notion",\n    readableCollectionId: "my-collection-id",\n    authentication: {\n        client_id: "YOUR_CLIENT_ID",\n        client_secret: "YOUR_CLIENT_SECRET",\n        redirect_uri: "https://your-app.com/callback"\n    },\n    syncImmediately: false  // BYOC flows cannot sync immediately\n});\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST https://api.airweave.ai/source-connections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "Notion connection (BYOC)",
  "short_name": "notion",
  "readable_collection_id": "my-collection-id",
  "authentication": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uri": "https://your-app.com/callback"
  },
  "sync_immediately": false
}'
`
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "OAuth Application Setup"
    }), "\n", jsx(_components.h3, {
      children: "Required Redirect URIs"
    }), "\n", jsx(_components.p, {
      children: "When setting up your OAuth application for BYOC, you'll need to add Airweave's callback URL as an allowed redirect URI:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "https://api.airweave.ai/oauth/callback\n"
      })
    }), "\n", jsx(_components.h3, {
      children: "Required Scopes"
    }), "\n", jsx(_components.p, {
      children: "Each connector requires specific OAuth scopes to function properly. Check the individual connector documentation for the required scopes."
    }), "\n", jsx(_components.h3, {
      children: "Example: GitHub OAuth Application Setup"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "Go to GitHub Settings → Developer settings → OAuth Apps"
      }), "\n", jsx(_components.li, {
        children: 'Click "New OAuth App"'
      }), "\n", jsxs(_components.li, {
        children: ["Fill in the application details:", "\n", jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Application name"
            }), ": Your application name"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Homepage URL"
            }), ": Your application URL"]
          }), "\n", jsxs(_components.li, {
            children: [jsx(_components.strong, {
              children: "Authorization callback URL"
            }), ": ", jsx(_components.code, {
              children: "https://api.airweave.ai/oauth/callback"
            })]
          }), "\n"]
        }), "\n"]
      }), "\n", jsx(_components.li, {
        children: "Note down the Client ID and Client Secret for use in your BYOC connection"
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Getting Help"
    }), "\n", jsxs(_components.p, {
      children: ["If you encounter issues not covered in this documentation, please reach out to us at ", jsx(_components.strong, {
        children: jsx(_components.a, {
          href: "mailto:hello@airweave.ai",
          children: "hello@airweave.ai"
        })
      }), " or check our ", jsx(_components.a, {
        href: "/api-reference",
        children: "API Reference"
      }), " for more detailed information about the OAuth endpoints."]
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
