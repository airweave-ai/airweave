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
    li: "li",
    p: "p",
    strong: "strong",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  }, { Icon } = _components;
  if (!Icon) _missingMdxReference("Icon");
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "Airweave connects to your apps, databases, and documents, then turns them into knowledge you can search. To understand how it works, you only need a few core concepts."
    }), "\n", jsxs(_components.h2, {
      children: [jsx(Icon, {
        icon: "fa-solid fa-database",
        size: "5",
        color: "#4199D3"
      }), " Source"]
    }), "\n", jsxs(_components.p, {
      children: ["A ", jsx(_components.strong, {
        children: "Source"
      }), " is a specific application, database, or workspace that Airweave has a connector for. Sources are the external systems where your data lives."]
    }), "\n", jsxs(_components.p, {
      children: [jsx(_components.strong, {
        children: "Examples:"
      }), " Zendesk, GitHub, Google Drive, Notion, PostgreSQL, Stripe"]
    }), "\n", jsxs(_components.h2, {
      children: [jsx(Icon, {
        icon: "fa-solid fa-plug",
        size: "5",
        color: "#4199D3"
      }), " Connector"]
    }), "\n", jsxs(_components.p, {
      children: ["A ", jsx(_components.strong, {
        children: "Connector"
      }), " is the integration that Airweave provides for a source. It defines what data types can be synced, how authentication works, and the specific entities that can be extracted."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Examples:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Zendesk connector (for tickets, users, organizations)"
      }), "\n", jsx(_components.li, {
        children: "GitHub connector (for repositories, issues, pull requests)"
      }), "\n", jsx(_components.li, {
        children: "Google Drive connector (for documents, folders, comments)"
      }), "\n"]
    }), "\n", jsxs(_components.h2, {
      children: [jsx(Icon, {
        icon: "fa-solid fa-link",
        size: "5",
        color: "#4199D3"
      }), " Source Connection"]
    }), "\n", jsxs(_components.p, {
      children: ["A ", jsx(_components.strong, {
        children: "Source Connection"
      }), " is a live connection created from a connector between Airweave and a specific source using your credentials. In that sense, each connection represents an authenticated and synced instance of connection between Airweave and a source."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Examples:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "A live connection between Airweave and a Zendesk workspace"
      }), "\n", jsx(_components.li, {
        children: "A live connection between Airweave and a specific GitHub repository"
      }), "\n"]
    }), "\n", jsxs(_components.h2, {
      children: [jsx(Icon, {
        icon: "fa-solid fa-file-alt",
        size: "5",
        color: "#4199D3"
      }), " Entity"]
    }), "\n", jsxs(_components.p, {
      children: ["An ", jsx(_components.strong, {
        children: "Entity"
      }), " is an individual data item pulled from a source. These are the actual pieces of data that get synced and made searchable."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Examples:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "A Zendesk ticket or message"
      }), "\n", jsx(_components.li, {
        children: "A GitHub issue or pull request"
      }), "\n", jsx(_components.li, {
        children: "A Google Doc or spreadsheet"
      }), "\n", jsx(_components.li, {
        children: "A database table row"
      }), "\n"]
    }), "\n", jsxs(_components.h2, {
      children: [jsx(Icon, {
        icon: "fa-solid fa-layer-group",
        size: "5",
        color: "#4199D3"
      }), " Collection"]
    }), "\n", jsxs(_components.p, {
      children: ["A ", jsx(_components.strong, {
        children: "Collection"
      }), " is a searchable knowledge base made up of synced data from one or more source connections. When you search a collection, queries run across all entities from all its connected sources."]
    }), "\n", jsx(_components.p, {
      children: jsx(_components.strong, {
        children: "Key features:"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Unified search interface across multiple sources"
      }), "\n", jsx(_components.li, {
        children: "Vector embeddings for semantic search"
      }), "\n", jsx(_components.li, {
        children: "Real-time data synchronization"
      }), "\n", jsx(_components.li, {
        children: "Configurable search parameters and filters"
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
