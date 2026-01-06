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
    table: "table",
    tbody: "tbody",
    td: "td",
    th: "th",
    thead: "thead",
    tr: "tr",
    ...useMDXComponents(),
    ...props.components
  }, { Accordion, Card, ParamField } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
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
        alt: "Ctti logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Ctti"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "CTTI source connector integrates with the AACT PostgreSQL database to extract trials."
    }), "\n", jsx(_components.p, {
      children: "Connects to the Aggregate Analysis of ClinicalTrials.gov database."
    }), "\n", jsx(_components.p, {
      children: "It creates web entities that link to\nClinicalTrials.gov pages."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/ctti.py",
      children: jsx(_components.p, {
        children: "Explore the Ctti connector implementation"
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
        children: "CTTI Clinical Trials authentication credentials schema."
      }), jsx(ParamField, {
        path: "username",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Username for the AACT Clinical Trials database"
        })
      }), jsx(ParamField, {
        path: "password",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Password for the AACT Clinical Trials database"
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "The following configuration options are available for this connector:"
    }), "\n", jsxs(Card, {
      title: "Configuration Parameters",
      className: "config-card",
      style: {
        backgroundColor: "rgba(0, 0, 0, 0.05)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: [jsx(_components.p, {
        children: "CTTI AACT configuration schema."
      }), jsx(ParamField, {
        path: "limit",
        type: "int",
        required: false,
        default: 1e4,
        children: jsx(_components.p, {
          children: "Maximum number of clinical trial studies to fetch from AACT database"
        })
      }), jsx(ParamField, {
        path: "skip",
        type: "int",
        required: false,
        default: 0,
        children: jsx(_components.p, {
          children: "Number of clinical trial studies to skip (for pagination). Use with limit to fetch different batches."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "CTTIWebEntity",
      children: [jsx(_components.p, {
        children: "Web entity for CTTI clinical trials."
      }), jsx(_components.p, {
        children: 'Represents a clinical trial study from ClinicalTrials.gov with an NCT ID.\n"WebFileEntity",\n"WebFileEntity",\nThis entity will be processed by the web_fetcher transformer to download\nthe actual clinical trial content from ClinicalTrials.gov.'
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
              children: "nct_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The NCT ID of the clinical trial study"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "study_url"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The full URL to the clinical trial study on ClinicalTrials.gov"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "data_source"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The source of the clinical trial data"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Additional metadata about the clinical trial"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "breadcrumbs"
            }), jsx(_components.td, {
              children: "List[Breadcrumb]"
            }), jsx(_components.td, {
              children: "List of breadcrumbs for this clinical trial entity"
            })]
          })]
        })]
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
