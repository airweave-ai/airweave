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
    code: "code",
    h2: "h2",
    h3: "h3",
    li: "li",
    ol: "ol",
    p: "p",
    ...useMDXComponents(),
    ...props.components
  }, { Card, ParamField } = _components;
  if (!Card) _missingMdxReference("Card");
  if (!ParamField) _missingMdxReference("ParamField");
  return jsxs(Fragment, {
    children: ["\n", jsxs("div", {
      className: "connector-header",
      children: [jsx("img", {
        src: "icon.svg",
        alt: "Sqlite logo",
        width: "72",
        height: "72",
        className: "connector-icon"
      }), jsxs("div", {
        className: "connector-info",
        children: [jsx("h1", {
          children: "Sqlite"
        }), jsx("p", {
          children: "Connect your Sqlite data to Airweave"
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Overview"
    }), "\n", jsx(_components.p, {
      children: "The Sqlite connector allows you to sync data from Sqlite into Airweave, making it available for search and retrieval by your agents."
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.h3, {
      children: "SQLiteSource"
    }), "\n", jsx(_components.p, {
      children: "SQLite source implementation."
    }), "\n", jsx(_components.p, {
      children: "This source connects to a SQLite database and generates entities for each table.\nIt uses database introspection to:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "Discover tables and their structures"
      }), "\n", jsx(_components.li, {
        children: "Create appropriate entity classes dynamically"
      }), "\n", jsx(_components.li, {
        children: "Generate entities for each table's data"
      }), "\n"]
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/sqlite.py",
      children: jsx(_components.p, {
        children: "Explore the Sqlite connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses a custom authentication configuration class: ", jsx(_components.code, {
        children: "SQLiteAuthConfig"
      }), "."]
    }), "\n", jsxs(Card, {
      title: "Authentication Configuration",
      className: "auth-config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "SQLite authentication configuration."
      }), jsx(ParamField, {
        path: "host",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The host of the SQLite database"
        })
      }), jsx(ParamField, {
        path: "port",
        type: "int",
        required: true,
        children: jsx(_components.p, {
          children: "The port of the SQLite database"
        })
      }), jsx(ParamField, {
        path: "database",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The name of the SQLite database"
        })
      }), jsx(ParamField, {
        path: "user",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The username for the SQLite database"
        })
      }), jsx(ParamField, {
        path: "password",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The password for the SQLite database"
        })
      }), jsx(ParamField, {
        path: "schema",
        type: "str",
        required: false,
        default: "public",
        children: jsx(_components.p, {
          children: "The schema of the SQLite database"
        })
      }), jsx(ParamField, {
        path: "tables",
        type: "str",
        required: false,
        default: "*",
        children: jsx(_components.p, {
          children: "Comma separated list of tables to sync. For example, 'users,orders'. For all tables, use '*'"
        })
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
