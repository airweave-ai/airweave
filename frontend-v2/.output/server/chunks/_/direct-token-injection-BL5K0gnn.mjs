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
      children: "Use case"
    }), "\n", jsx(_components.p, {
      children: "If you embed Airweave inside your own product you might already manage OAuth 2.0 tokens for your users.\nIn that case, you do not want to have to ask them to click through a second consent screen for Airweave.\nAirweave therefore allows you to provide existing tokens to Airweave directly, so that"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Your service owns token storage and rotation."
      }), "\n", jsx(_components.li, {
        children: "Airweave consumes the tokens solely for data sync."
      }), "\n", jsx(_components.li, {
        children: "No additional user interaction required."
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "There are two common scenarios:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Create a new source connection"
        }), " by sending the access token."]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Trigger a sync"
        }), " on an existing source connection using stored credentials."]
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "The next sections walk you through both flows."
    }), "\n", jsx(_components.h2, {
      children: "Create a source connection with your own tokens"
    }), "\n", jsxs(_components.p, {
      children: ["Skip the OAuth 2.0 flow entirely by sending your own tokens in the ", jsx(_components.code, {
        children: "POST /source-connections"
      }), " call. You are responsible for acquiring and storing these tokens, Airweave simply uses what you provide."]
    }), "\n", jsx(_components.p, {
      children: "Creating a source connection with direct tokens looks like this:"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-Python",
          children: 'from airweave import AirweaveSDK\nfrom airweave.types import OAuthTokenAuthentication\n\nairweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")\n\nsource_connection = airweave.source_connections.create(\n    name="Asana connection",\n    short_name="asana",\n    readable_collection_id="my-collection-id",\n    authentication=OAuthTokenAuthentication(\n        access_token="YOUR_ACCESS_TOKEN",\n    ),\n    sync_immediately=True\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});\n\nconst sourceConnection = await airweave.sourceConnections.create({\n    name: "Asana connection",\n    shortName: "asana",\n    readableCollectionId: "my-collection-id",\n    authentication: {\n        type: "oauth_token",\n        accessToken: "YOUR_ACCESS_TOKEN",\n        refreshToken: "YOUR_REFRESH_TOKEN"  // Optional\n    },\n    syncImmediately: true\n});\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: `curl -X POST https://api.airweave.ai/source-connections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "Asana connection",
  "short_name": "asana",
  "readable_collection_id": "my-collection-id",
  "authentication": {
    "type": "oauth_token",
    "access_token": "YOUR_ACCESS_TOKEN",
    "refresh_token": "YOUR_REFRESH_TOKEN"
  },
  "sync_immediately": true
}'
`
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Trigger a sync"
    }), "\n", jsxs(_components.p, {
      children: [jsxs(Note, {
        children: ["The run endpoint uses the stored credentials from the source connection. To use different credentials, create a new source connection with ", jsx(_components.code, {
          children: "OAuthTokenAuthentication"
        }), "."]
      }), "\nBy default, Airweave uses the credentials obtained during the initial OAuth 2.0 handshake to run a data synchronization job."]
    }), "\n", jsx(_components.p, {
      children: "Here is an example:"
    }), "\n", jsxs(CodeBlocks, {
      children: [jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-Python",
          children: 'from airweave import AirweaveSDK\n\nairweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")\n\njob = airweave.source_connections.run(\n    source_connection_id="source_connection_id"\n)\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-javascript",
          children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", baseUrl: "https://api.airweave.ai"});\n\nconst job = await airweave.sourceConnections.run(\n    "source_connection_id"\n);\n'
        })
      }), jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-bash",
          children: 'curl -X POST https://api.airweave.ai/source-connections/source_connection_id/run \\\n     -H "x-api-key: <apiKey>" \\\n     -H "Content-Type: application/json"\n'
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Auth provider connections"
    }), "\n", jsxs(_components.p, {
      children: ["Airweave also supports creating source connections through auth providers like Composio and Pipedream. Check out the ", jsx(_components.a, {
        href: "/auth-providers",
        children: "Authentication Providers documentation"
      }), " to learn more."]
    }), "\n", jsxs(_components.p, {
      children: ["If you have an edge case that isn't covered by these features, please let us know at ", jsx(_components.strong, {
        children: jsx(_components.a, {
          href: "mailto:hello@airweave.ai",
          children: "hello@airweave.ai"
        })
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
