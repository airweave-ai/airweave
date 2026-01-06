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
    h2: "h2",
    hr: "hr",
    p: "p",
    ...useMDXComponents(),
    ...props.components
  }, { Card, CardGroup } = _components;
  if (!Card) _missingMdxReference("Card");
  if (!CardGroup) _missingMdxReference("CardGroup");
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "Airweave is an open-source context retrieval layer that gives AI agents unified search across all your apps, databases, and documents. Instead of wiring each data source separately, Airweave connects directly to all of your existing tools and exposes their data through a single search interface."
    }), "\n", jsx(_components.p, {
      children: "Airweave continuously syncs information from connected sources and makes it available as a unified, searchable knowledge base. This allows AI agents to retrieve current, source-grounded context at query time, rather than relying on static embeddings or custom data pipelines that quickly fall out of date."
    }), "\n", jsxs(CardGroup, {
      cols: 2,
      children: [jsx(Card, {
        title: "Get Started",
        icon: "fa-solid fa-rocket",
        href: "/quickstart",
        children: jsx(_components.p, {
          children: "Follow our quickstart guide to get up and running with Airweave in minutes"
        })
      }), jsx(Card, {
        title: "Try the Platform",
        icon: "fa-solid fa-globe",
        href: "https://app.airweave.ai",
        children: jsx(_components.p, {
          children: "Access the hosted Airweave platform"
        })
      }), jsx(Card, {
        title: "Join Discord",
        icon: "fa-brands fa-discord",
        href: "https://discord.gg/484HY9Ehxt",
        children: jsx(_components.p, {
          children: "Get help from our community and team"
        })
      }), jsx(Card, {
        title: "View on GitHub",
        icon: "fa-brands fa-github",
        href: "https://github.com/airweave-ai/airweave",
        children: jsx(_components.p, {
          children: "Star the repo and contribute to the project"
        })
      })]
    }), "\n", jsx(_components.hr, {}), "\n", jsx(_components.h2, {
      children: "Who it's for"
    }), "\n", jsx(_components.p, {
      children: "Developers and teams building AI agents and other AI-powered applications that need reliable access to information across multiple tools and data sources."
    }), "\n", jsx(_components.p, {
      children: "If you're working on long-running AI agents, retrieval-augmented generation, or any context-heavy LLM application, Airweave provides the infrastructure to retrieve and manage context without maintaining bespoke integrations for every data source."
    }), "\n", jsx(_components.h2, {
      children: "Use cases"
    }), "\n", jsx(_components.p, {
      children: "Airweave lets AI agents search across company knowledge bases, cloud drives, databases, and SaaS tools in a single query."
    }), "\n", jsx(_components.p, {
      children: "Common use cases include:"
    }), "\n", jsxs(CardGroup, {
      cols: 3,
      children: [jsx(Card, {
        title: "Internal Knowledge Assistants",
        icon: "fa-solid fa-brain",
        children: jsx(_components.p, {
          children: "Pull information from tools like Notion, Google Drive, and Slack"
        })
      }), jsx(Card, {
        title: "Customer Support Agents",
        icon: "fa-solid fa-headset",
        children: jsx(_components.p, {
          children: "Access context from tickets, docs, and CRM systems"
        })
      }), jsx(Card, {
        title: "Multi-Source Context Retrieval",
        icon: "fa-solid fa-database",
        children: jsx(_components.p, {
          children: "Retrieve and combine relevant context from structured and unstructured sources at query time."
        })
      })]
    }), "\n", jsx(_components.p, {
      children: "In all cases, Airweave helps agents retrieve facts from the right source instead of guessing or relying on incomplete context."
    }), "\n", jsx(_components.h2, {
      children: "Where to go next"
    }), "\n", jsxs(CardGroup, {
      cols: 3,
      children: [jsx(Card, {
        title: "Quickstart",
        icon: "fa-solid fa-play",
        href: "/quickstart",
        children: jsx(_components.p, {
          children: "Set up your first Airweave collection and start syncing data"
        })
      }), jsx(Card, {
        title: "Concepts",
        icon: "fa-solid fa-book",
        href: "/concepts",
        children: jsx(_components.p, {
          children: "Learn about Airweave's core architecture and how it works"
        })
      }), jsx(Card, {
        title: "Homepage",
        icon: "fa-solid fa-home",
        href: "https://airweave.ai",
        children: jsx(_components.p, {
          children: "High-level overview and latest product updates"
        })
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
