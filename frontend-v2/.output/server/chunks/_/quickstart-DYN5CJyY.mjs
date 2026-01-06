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
    p: "p",
    pre: "pre",
    ...useMDXComponents(),
    ...props.components
  }, { Card, CardGroup, CodeBlocks, Step, Steps } = _components;
  if (!Card) _missingMdxReference("Card");
  if (!CardGroup) _missingMdxReference("CardGroup");
  if (!CodeBlocks) _missingMdxReference("CodeBlocks");
  if (!Step) _missingMdxReference("Step");
  if (!Steps) _missingMdxReference("Steps");
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "Follow this guide to get up and running with Airweave in just a few steps."
    }), "\n", jsxs(Steps, {
      children: [jsxs(Step, {
        title: "Choose your deployment",
        toc: true,
        children: [jsxs(_components.p, {
          children: ["The simplest way to use Airweave is through our hosted cloud platform at ", jsx(_components.a, {
            href: "https://app.airweave.ai",
            children: "app.airweave.ai"
          }), "."]
        }), jsxs(_components.p, {
          children: ["If you prefer to run Airweave yourself, you can deploy it locally on macOS, Linux or WSL. After cloning the repository and starting the server, you will be able to open the dashboard at ", jsx(_components.a, {
            href: "http://localhost:8080",
            children: "http://localhost:8080"
          })]
        }), jsx(_components.pre, {
          children: jsx(_components.code, {
            className: "language-bash",
            children: "git clone https://github.com/airweave-ai/airweave.git\ncd airweave\n./start.sh\n"
          })
        })]
      }), jsxs(Step, {
        title: "Set-up Airweave client",
        toc: true,
        children: [jsx(_components.p, {
          children: "Airweave provides SDKs for Python and Node.js. Install the package."
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: "pip install airweave-sdk\n"
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: "npm install @airweave/sdk\n"
            })
          })]
        }), jsx(_components.p, {
          children: "Now, create and copy your API key from your Airweave dashboard."
        }), jsx("video", {
          src: "./airweave_api_key.mp4",
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
        }), jsxs(_components.p, {
          children: ["Initialize the Airweave client with your new API key. For local deployments, set base_url to ", jsx(_components.code, {
            children: '"http://localhost:8001"'
          }), "."]
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-Python",
              children: 'from airweave import AirweaveSDK\n\nairweave = AirweaveSDK(api_key="YOUR_API_KEY", base_url="https://api.airweave.ai")\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-javascript",
              children: 'import { AirweaveSDKClient } from "@airweave/sdk";\n\nconst airweave = new AirweaveSDKClient({apiKey: "YOUR_API_KEY", base_url: "https://api.airweave.ai"});\n'
            })
          })]
        })]
      }), jsxs(Step, {
        title: "Create a collection",
        toc: true,
        children: [jsx(_components.p, {
          children: "A collection is a group of different data sources that you can search using a single endpoint."
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-Python",
              children: 'collection = airweave.collections.create(name="My First Collection")\n\nprint(f"Created collection: {collection.readable_id}")\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-javascript",
              children: 'const collection = await airweave.collections.create({name: "My First Collection"});\n\nconsole.log(`Created collection: ${collection.readable_id}`);\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: `curl -X POST 'https://api.airweave.ai/collections' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "name": "My First Collection"
  }'
`
            })
          })]
        })]
      }), jsxs(Step, {
        title: "Add source connection(s) to your collection",
        toc: true,
        children: [jsx(_components.p, {
          children: "A source connection links a specific app or database to your collection. It handles authentication and automatically syncs data."
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-Python",
              children: 'source_connection = airweave.source_connections.create(\n    name="My Stripe Connection",\n    short_name="stripe",\n    readable_collection_id=collection.readable_id,\n    authentication={\n        "credentials": {\n            "api_key": "your_stripe_api_key"  # Replace with real API key\n        }\n    }\n)\n\nprint(f"Status: {source_connection.status}")\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-javascript",
              children: 'const sourceConnection = await airweave.sourceConnections.create({\n  name: "My Stripe Connection",\n  short_name: "stripe",\n  readable_collection_id: collection.readable_id,\n  authentication: {\n    credentials: {\n      api_key: "SK_TEST_YOUR_STRIPE_API_KEY"\n    }\n  }\n});\n\nconsole.log(`Status: ${sourceConnection.status}`);\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: `curl -X POST 'https://api.airweave.ai/source-connections' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "name": "My Stripe Connection",
    "short_name": "stripe",
    "readable_collection_id": "my-first-collection-abc123",
    "authentication": {
      "credentials": {
        "api_key": "SK_TEST_YOUR_STRIPE_API_KEY"
      }
    }
  }'
`
            })
          })]
        })]
      }), jsxs(Step, {
        title: "Search your collection",
        toc: true,
        children: [jsx(_components.p, {
          children: "You can now search your collection and get the most relevant results from all connected sources."
        }), jsxs(CodeBlocks, {
          children: [jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-Python",
              children: 'results = airweave.collections.search(\n    readable_id=collection.readable_id,\n    query="Find returned payments from user John Doe?",\n)\n\nfor result in results.results:\n  print(result)\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-javascript",
              children: 'const results = await airweave.collections.search(\n  collection.readable_id,\n  { query: "Find returned payments from user John Doe?" }\n);\n\nresults.results.forEach(result => {\n  console.log(result);\n});\n'
            })
          }), jsx(_components.pre, {
            children: jsx(_components.code, {
              className: "language-bash",
              children: "curl -X GET 'https://api.airweave.ai/collections/my-first-collection-abc123/search?query=Find%20returned%20payments%20from%20user%20John%20Doe%3F' \\\n  -H 'x-api-key: YOUR_API_KEY'\n"
            })
          })]
        })]
      })]
    }), "\n", jsx(_components.p, {
      children: "You've now successfully deployed Airweave, connected your first data source, and searched your first collection. To continue, you can explore more integrations and dive into the API reference. For community and support, check out the links below."
    }), "\n", jsxs(CardGroup, {
      cols: 2,
      children: [jsxs(Card, {
        title: "GitHub Repository",
        icon: "fa-brands fa-github",
        href: "https://github.com/airweave-ai/airweave",
        children: [jsx(_components.p, {
          children: "Join our growing open-source community."
        }), jsx(_components.p, {
          children: "View code, contribute, and report issues."
        })]
      }), jsxs(Card, {
        title: "Community Support",
        icon: "fa-brands fa-discord",
        href: "https://discord.gg/484HY9Ehxt",
        children: [jsx(_components.p, {
          children: "Get help from our team and community."
        }), jsx(_components.p, {
          children: "Share feedback and feature requests."
        })]
      })]
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
