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
    p: "p",
    strong: "strong",
    ...useMDXComponents(),
    ...props.components
  }, { Step, Steps } = _components;
  if (!Step) _missingMdxReference("Step");
  if (!Steps) _missingMdxReference("Steps");
  return jsxs(Fragment, {
    children: [jsx(_components.h2, {
      children: "Introduction"
    }), "\n", jsxs(_components.p, {
      children: ["Authentication providers let you reuse existing authenticated connections from third-party platforms such as ", jsx(_components.strong, {
        children: "Composio"
      }), " or ", jsx(_components.strong, {
        children: "Pipedream"
      }), ". Instead of requiring users to sign in separately for each service, Airweave integrates with these providers and automatically pulls credentials when needed. This reduces setup time and eliminates duplicate authentication steps."]
    }), "\n", jsx(_components.h2, {
      children: "How It Works"
    }), "\n", jsx(_components.p, {
      children: "Authentication providers enable Airweave to leverage these existing connections through a simple three-step process:"
    }), "\n", jsxs(Steps, {
      children: [jsx(Step, {
        title: "Connect Provider",
        toc: true,
        children: jsx(_components.p, {
          children: "Add your provider credentials in Airweave"
        })
      }), jsx(Step, {
        title: "Configure Source",
        toc: true,
        children: jsx(_components.p, {
          children: "Select the existing connection you want to reuse when creating a data source."
        })
      }), jsx(Step, {
        title: "Automatic Retrieval",
        toc: true,
        children: jsx(_components.p, {
          children: "Credentials are fetched automatically during sync operations"
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
