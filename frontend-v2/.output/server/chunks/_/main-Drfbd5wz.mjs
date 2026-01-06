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
    h3: "h3",
    p: "p",
    ...useMDXComponents(),
    ...props.components
  }, { Card, ParamField } = _components;
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
        alt: "Postgresql logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Postgresql"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "PostgreSQL source connector integrates with PostgreSQL databases to extract structured data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from database tables."
    }), "\n", jsx(_components.p, {
      children: "It uses dynamic schema introspection to create appropriate entity classes\nand provides comprehensive access to relational data with proper type mapping and relationships."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/postgresql.py",
      children: jsx(_components.p, {
        children: "Explore the Postgresql connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsx(_components.p, {
      children: "This connector uses a custom authentication configuration."
    }), "\n", jsxs(Card, {
      title: "Authentication Configuration",
      className: "auth-config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "PostgreSQL authentication configuration."
      }), jsx(ParamField, {
        path: "host",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The host of the PostgreSQL database"
        })
      }), jsx(ParamField, {
        path: "port",
        type: "int",
        required: true,
        children: jsx(_components.p, {
          children: "The port of the PostgreSQL database"
        })
      }), jsx(ParamField, {
        path: "database",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The name of the PostgreSQL database"
        })
      }), jsx(ParamField, {
        path: "user",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The username for the PostgreSQL database"
        })
      }), jsx(ParamField, {
        path: "password",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The password for the PostgreSQL database"
        })
      }), jsx(ParamField, {
        path: "schema",
        type: "str",
        required: false,
        default: "public",
        children: jsx(_components.p, {
          children: "The schema of the PostgreSQL database"
        })
      }), jsx(ParamField, {
        path: "tables",
        type: "str",
        required: false,
        default: "*",
        children: jsx(_components.p, {
          children: "Comma separated list of tables and views to sync. For example, 'users,orders'. For all tables (not views), use '*'."
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "This connector does not have any additional configuration options."
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
