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
    li: "li",
    p: "p",
    pre: "pre",
    table: "table",
    tbody: "tbody",
    td: "td",
    th: "th",
    thead: "thead",
    tr: "tr",
    ul: "ul",
    ...useMDXComponents(),
    ...props.components
  };
  return jsxs(Fragment, {
    children: [jsx(_components.p, {
      children: "API requests are rate-limited per organization based on your billing plan. Limits are enforced per minute using a sliding window."
    }), "\n", jsx(_components.h2, {
      children: "Limits by Plan"
    }), "\n", jsxs(_components.table, {
      children: [jsx(_components.thead, {
        children: jsxs(_components.tr, {
          children: [jsx(_components.th, {
            children: "Plan"
          }), jsx(_components.th, {
            children: "Requests per Minute"
          })]
        })
      }), jsxs(_components.tbody, {
        children: [jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: "Developer"
          }), jsx(_components.td, {
            children: "10"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: "Pro"
          }), jsx(_components.td, {
            children: "100"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: "Team"
          }), jsx(_components.td, {
            children: "250"
          })]
        }), jsxs(_components.tr, {
          children: [jsx(_components.td, {
            children: "Enterprise"
          }), jsx(_components.td, {
            children: "Unlimited"
          })]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Rate Limit Headers"
    }), "\n", jsx(_components.p, {
      children: "All API responses include rate limit information:"
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "RateLimit-Limit: 100\nRateLimit-Remaining: 95\nRateLimit-Reset: 1729012345\n"
      })
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "RateLimit-Limit"
        }), ": Maximum requests per minute"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "RateLimit-Remaining"
        }), ": Requests left in current window"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "RateLimit-Reset"
        }), ": Unix timestamp when limit resets"]
      }), "\n"]
    }), "\n", jsx(_components.h2, {
      children: "Rate Limit Exceeded"
    }), "\n", jsxs(_components.p, {
      children: ["When you exceed your limit, you'll receive a ", jsx(_components.code, {
        children: "429 Too Many Requests"
      }), " response with a ", jsx(_components.code, {
        children: "Retry-After"
      }), " header indicating seconds until you can retry."]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        className: "language-json",
        children: '{\n  "detail": "Rate limit exceeded. Try again in 42 seconds."\n}\n'
      })
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
export {
  MDXContent as default
};
