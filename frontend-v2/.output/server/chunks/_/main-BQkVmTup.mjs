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
    h1: "h1",
    h2: "h2",
    h3: "h3",
    h4: "h4",
    hr: "hr",
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
  }, { Accordion, Callout, Card } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
  if (!Callout) _missingMdxReference("Callout");
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
        alt: "Slack logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Slack"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Slack source connector using federated search."
    }), "\n", jsx(_components.p, {
      children: "Instead of syncing all messages and files, this source searches Slack at query time\nusing the search.all API endpoint. This is necessary because Slack's rate limits\nare too restrictive for full synchronization."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/slack.py",
      children: jsx(_components.p, {
        children: "Explore the Slack connector implementation"
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
      title: "SlackMessageEntity",
      children: [jsx(_components.p, {
        children: "Schema for Slack message entities from federated search."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://api.slack.com/methods/search.messages",
          children: "https://api.slack.com/methods/search.messages"
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
              children: "text"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The text content of the message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User ID of the message author"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "username"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Username of the message author"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ts"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Message timestamp (unique identifier)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "channel_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the channel containing this message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "channel_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the channel"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "channel_is_private"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Whether the channel is private"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Type of the message"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "permalink"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Permalink to the message in Slack"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "team"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Team/workspace ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "previous_message"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Previous message for context"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "next_message"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Next message for context"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "score"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Search relevance score from Slack"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "iid"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Internal search ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the message in Slack"
            })]
          })]
        })]
      })]
    }), "\n", "\n", jsx(_components.hr, {}), "\n", jsx(_components.h1, {
      children: "Federated Search"
    }), "\n", jsxs(Callout, {
      intent: "info",
      children: [jsx(_components.p, {
        children: jsx(_components.strong, {
          children: "Real-Time Search Without Syncing"
        })
      }), jsxs(_components.p, {
        children: ["The Slack connector uses ", jsx(_components.strong, {
          children: "federated search"
        }), " to query your Slack workspace in real-time at search time, rather than syncing all messages into Airweave's database. This approach:"]
      }), jsxs(_components.ul, {
        children: ["\n", jsx(_components.li, {
          children: "Avoids hitting Slack's strict rate limits"
        }), "\n", jsx(_components.li, {
          children: "Keeps your data in Slack (nothing synced to Airweave)"
        }), "\n", jsx(_components.li, {
          children: "Returns fresh, up-to-date results at query time"
        }), "\n", jsx(_components.li, {
          children: "Searches across all channels you have access to"
        }), "\n"]
      }), jsx(_components.p, {
        children: "When you search in Airweave, your query is automatically sent to Slack's search API, and results are merged with data from your other connected sources."
      })]
    }), "\n", jsx(_components.h2, {
      children: "How It Works"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Connect your Slack workspace"
        }), " using OAuth (one-time setup)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Search in Airweave"
        }), " - your queries are automatically sent to Slack's search API in real-time"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Results are merged"
        }), " with data from your other sources using intelligent ranking"]
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "No data is synced or stored in Airweave - everything happens at search time."
    }), "\n", jsx(_components.h2, {
      children: "Prerequisites"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Access to a Slack workspace where you have permissions to add apps"
      }), "\n", jsx(_components.li, {
        children: "Administrator access to your Airweave instance"
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Setup Steps"
    }), "\n", jsx(_components.h3, {
      children: "Option A: Production Setup (OAuth Flow)"
    }), "\n", jsx(_components.p, {
      children: "When running Airweave in production (non-localhost), simply:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "Navigate to your Airweave collection"
      }), "\n", jsx(_components.li, {
        children: 'Click "Add Source" and select "Slack"'
      }), "\n", jsx(_components.li, {
        children: "Follow the OAuth flow to authorize Airweave"
      }), "\n", jsx(_components.li, {
        children: "That's it! Your Slack workspace is now searchable"
      }), "\n"]
    }), "\n", jsxs(_components.p, {
      children: ["The OAuth flow will request the ", jsx(_components.code, {
        children: "search:read"
      }), " user scope, which allows Airweave to search on your behalf."]
    }), "\n", jsx(_components.h3, {
      children: "Option B: Local Development Setup (Manual Token)"
    }), "\n", jsxs(_components.p, {
      children: ["Slack does not allow OAuth2 flows for ", jsx(_components.code, {
        children: "http://localhost"
      }), ", so for local development you'll need to manually create a token."]
    }), "\n", jsx(_components.h4, {
      children: "1. Create a Slack App"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: ["Go to ", jsx(_components.a, {
          href: "https://api.slack.com/apps",
          children: "https://api.slack.com/apps"
        })]
      }), "\n", jsx(_components.li, {
        children: 'Click the "Create New App" button'
      }), "\n", jsx(_components.li, {
        children: 'Choose "From scratch"'
      }), "\n", jsx(_components.li, {
        children: 'Enter a name for your app (e.g., "Airweave Local Dev")'
      }), "\n", jsx(_components.li, {
        children: "Select the workspace you want to connect"
      }), "\n", jsx(_components.li, {
        children: 'Click "Create App"'
      }), "\n"]
    }), "\n", jsx("img", {
      src: "create-app.png",
      alt: "Create app in Slack",
      width: "600"
    }), "\n", jsx(_components.h4, {
      children: "2. Configure OAuth Permissions"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: 'In your Slack app settings, navigate to "OAuth & Permissions" in the sidebar'
      }), "\n", jsx(_components.li, {
        children: 'Scroll down to the "Scopes" section'
      }), "\n", jsxs(_components.li, {
        children: ['Under "User Token Scopes", add the following scope:', "\n", jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: [jsx(_components.code, {
              children: "search:read"
            }), " (required for federated search)"]
          }), "\n"]
        }), "\n"]
      }), "\n"]
    }), "\n", jsx("img", {
      src: "user-token-scopes.png",
      alt: "User Token Scopes",
      width: "600"
    }), "\n", jsxs(Callout, {
      intent: "warning",
      children: [jsx(_components.p, {
        children: jsx(_components.strong, {
          children: "Scope Requirements"
        })
      }), jsxs(_components.p, {
        children: ["For federated search, you only need the ", jsx(_components.code, {
          children: "search:read"
        }), " user scope. This allows Airweave to search Slack on your behalf at query time."]
      }), jsxs(_components.p, {
        children: ["If you see scopes like ", jsx(_components.code, {
          children: "channels:history"
        }), ", ", jsx(_components.code, {
          children: "channels:read"
        }), ", ", jsx(_components.code, {
          children: "users:read"
        }), " in older documentation, those were for the legacy sync-based approach and are no longer needed."]
      })]
    }), "\n", jsx(_components.h4, {
      children: "3. Install the App to Your Workspace"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: 'Scroll back to the top of the "OAuth & Permissions" page'
      }), "\n", jsxs(_components.li, {
        children: ["Click the ", jsx(_components.strong, {
          children: "Install to Workspace"
        }), " button"]
      }), "\n", jsx(_components.li, {
        children: 'Review the permissions and click "Allow"'
      }), "\n", jsx(_components.li, {
        children: "After installation, you'll be redirected back to the app settings"
      }), "\n", jsxs(_components.li, {
        children: ['Copy the "User OAuth Token" (it starts with ', jsx(_components.code, {
          children: "xoxp-"
        }), ")"]
      }), "\n"]
    }), "\n", jsx("img", {
      src: "oauth2-token.png",
      alt: "OAuth2 User token in Slack",
      width: "600"
    }), "\n", jsx(_components.h4, {
      children: "4. Add the Token to Airweave"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "In your Airweave application, navigate to the integrations section"
      }), "\n", jsx(_components.li, {
        children: 'Select "Slack" from the available integrations'
      }), "\n", jsx(_components.li, {
        children: 'Choose "Direct Token Injection"'
      }), "\n", jsx(_components.li, {
        children: "Paste the User OAuth Token you copied in the previous step"
      }), "\n", jsx(_components.li, {
        children: "Save your changes"
      }), "\n"]
    }), "\n", jsx("img", {
      src: "add-token-in-airweave.png",
      alt: "Add Slack token in Airweave",
      width: "600"
    }), "\n", jsx(_components.h2, {
      children: "Verification"
    }), "\n", jsx(_components.p, {
      children: "After completing these steps, try searching in your Airweave collection. Your search query will be automatically sent to Slack, and relevant messages will appear in your search results alongside data from your other sources."
    }), "\n", jsx(_components.h2, {
      children: "Troubleshooting"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "No Slack results appearing"
        }), ": Verify the token was copied correctly and hasn't expired"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Permission errors"
        }), ": Ensure you've added the ", jsx(_components.code, {
          children: "search:read"
        }), " user scope to your Slack app"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Authentication failed"
        }), ": Try regenerating the token in Slack and updating it in Airweave"]
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
