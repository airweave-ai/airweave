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
    strong: "strong",
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
      children: [jsx("img", {
        src: "icon.svg",
        alt: "Intercom logo",
        width: "72",
        height: "72",
        className: "connector-icon"
      }), jsxs("div", {
        className: "connector-info",
        children: [jsx("h1", {
          children: "Intercom"
        }), jsx("p", {
          children: "Connect your Intercom data to Airweave"
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Overview"
    }), "\n", jsx(_components.p, {
      children: "The Intercom connector allows you to sync data from Intercom into Airweave, making it available for search and retrieval by your agents."
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.h3, {
      children: "IntercomSource"
    }), "\n", jsx(_components.p, {
      children: "Intercom source implementation."
    }), "\n", jsx(_components.p, {
      children: "This connector retrieves data from Intercom objects such as Contacts, Companies,\nConversations, and Tickets, then yields them as entities using their respective\nIntercom entity schemas."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/intercom.py",
      children: jsx(_components.p, {
        children: "Explore the Intercom connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses ", jsx(_components.strong, {
        children: "OAuth 2.0 authentication flow"
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
        children: "Intercom authentication credentials schema."
      }), jsx(ParamField, {
        path: "access_token",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The access token for your Intercom app."
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Entities"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "IntercomContactEntity",
      children: [jsx(_components.p, {
        children: "Schema for Intercom contact entities."
      }), jsx(_components.p, {
        children: "Contacts in Intercom can be either users or leads with associated profile data."
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
              children: "role"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The type of contact - either 'user' or 'lead'"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "external_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A unique identifier for the contact provided by your application"
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
              children: "phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The contact's phone number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The contact's full name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "avatar"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to the contact's avatar or profile image"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Creation time of the contact, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "updated_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Last updated time of the contact, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the contact has been archived"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "IntercomCompanyEntity",
      children: [jsx(_components.p, {
        children: "Schema for Intercom company entities."
      }), jsx(_components.p, {
        children: "Companies in Intercom represent organizations that your contacts belong to."
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
              children: "name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The company's name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "company_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A unique identifier for the company"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "plan"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The plan or subscription level of the company"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "monthly_spend"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "The monthly spend or revenue associated with this company"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "session_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The number of sessions associated with the company"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The number of users associated with the company"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "website"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The company's website URL"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Creation time of the company, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "updated_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Last updated time of the company, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the company has been archived"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "IntercomConversationEntity",
      children: [jsx(_components.p, {
        children: "Schema for Intercom conversation entities."
      }), jsx(_components.p, {
        children: "Conversations in Intercom represent message threads between contacts and your team."
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
              children: "conversation_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The unique identifier for the conversation in Intercom"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The title or subject of the conversation"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current state of the conversation (e.g., 'open', 'closed')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time the conversation was created, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "updated_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time the conversation was last updated, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the conversation has been archived"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "IntercomTicketEntity",
      children: [jsx(_components.p, {
        children: "Schema for Intercom ticket entities."
      }), jsx(_components.p, {
        children: "Tickets in Intercom represent structured support requests that can be tracked and managed."
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
              children: "The subject or title of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The detailed description of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The current state of the ticket (e.g., 'open', 'closed')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "contact_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The ID of the contact associated with this ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "company_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The ID of the company associated with this ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time the ticket was created, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "updated_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "The time the ticket was last updated, represented as UTC Unix timestamp"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "archived"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the ticket has been archived"
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
