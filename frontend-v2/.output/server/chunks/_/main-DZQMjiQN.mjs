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
    h2: "h2",
    h3: "h3",
    li: "li",
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
  }, { Accordion, Card } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
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
        alt: "Hubspot logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Hubspot"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "HubSpot source connector integrates with the HubSpot CRM API to extract CRM data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes customer relationship management data."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to contacts, companies, deals, and support tickets."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/hubspot.py",
      children: jsx(_components.p, {
        children: "Explore the Hubspot connector implementation"
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
      title: "HubspotContactEntity",
      children: [jsx(_components.p, {
        children: "Schema for HubSpot contact entities with flexible property handling."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.hubspot.com/docs/api/crm/contacts",
          children: "https://developers.hubspot.com/docs/api/crm/contacts"
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
              children: "first_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The contact's first name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The contact's last name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The contact's email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "All properties from HubSpot contact object"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the contact is archived"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "HubspotCompanyEntity",
      children: [jsx(_components.p, {
        children: "Schema for HubSpot company entities with flexible property handling."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.hubspot.com/docs/api/crm/companies",
          children: "https://developers.hubspot.com/docs/api/crm/companies"
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
              children: "domain"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The company's domain name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "All properties from HubSpot company object"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the company is archived"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "HubspotDealEntity",
      children: [jsx(_components.p, {
        children: "Schema for HubSpot deal entities with flexible property handling."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.hubspot.com/docs/api/crm/deals",
          children: "https://developers.hubspot.com/docs/api/crm/deals"
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
              children: "deal_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The name of the deal"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "The monetary value of the deal"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "All properties from HubSpot deal object"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the deal is archived"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "HubspotTicketEntity",
      children: [jsx(_components.p, {
        children: "Schema for HubSpot ticket entities with flexible property handling."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developers.hubspot.com/docs/api/crm/tickets",
          children: "https://developers.hubspot.com/docs/api/crm/tickets"
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
              children: "subject"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The subject of the support ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The content or description of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "properties"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "All properties from HubSpot ticket object"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the ticket is archived"
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
