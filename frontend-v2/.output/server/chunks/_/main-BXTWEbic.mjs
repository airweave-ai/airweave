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
        alt: "Salesforce logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Salesforce"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Salesforce source connector integrates with the Salesforce REST API to extract CRM data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes comprehensive data from your Salesforce org including:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsx(_components.li, {
        children: "Accounts (companies, organizations)"
      }), "\n", jsx(_components.li, {
        children: "Contacts (people, leads)"
      }), "\n", jsx(_components.li, {
        children: "Opportunities (deals, sales prospects)"
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "It provides access to all major Salesforce objects with proper OAuth2 authentication."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/salesforce.py",
      children: jsx(_components.p, {
        children: "Explore the Salesforce connector implementation"
      })
    }), "\n", jsx(_components.h3, {
      children: "Authentication"
    }), "\n", jsxs(_components.p, {
      children: ["This connector uses ", jsx(_components.strong, {
        children: "OAuth 2.0 with custom credentials"
      }), ". You need to provide your OAuth application's Client ID and Client Secret, then complete the OAuth consent flow."]
    }), "\n", jsx(Card, {
      title: "OAuth Setup Required",
      className: "auth-setup-card",
      style: {
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        padding: "16px",
        marginBottom: "24px"
      },
      children: jsxs(_components.ol, {
        children: ["\n", jsx(_components.li, {
          children: "Create an OAuth application in your provider's developer console"
        }), "\n", jsx(_components.li, {
          children: "Enter your Client ID and Client Secret when configuring the connection"
        }), "\n", jsx(_components.li, {
          children: "Complete the OAuth consent flow"
        }), "\n"]
      })
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
        children: "Salesforce configuration schema."
      }), jsx(ParamField, {
        path: "instance_url",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Your Salesforce instance domain only (e.g. 'mycompany.my.salesforce.com')"
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "SalesforceAccountEntity",
      children: [jsx(_components.p, {
        children: "Schema for Salesforce Account entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_account.htm",
          children: "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_account.htm"
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
              children: "account_number"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "website"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account website URL"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account phone number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fax"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account fax number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "industry"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account industry"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "annual_revenue"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Annual revenue"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "number_of_employees"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of employees"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ownership"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account ownership type"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ticker_symbol"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Stock ticker symbol"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "rating"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account rating"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of parent account"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Account type"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "billing_street"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Billing street address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "billing_city"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Billing city"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "billing_state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Billing state/province"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "billing_postal_code"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Billing postal code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "billing_country"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Billing country"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shipping_street"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Shipping street address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shipping_city"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Shipping city"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shipping_state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Shipping state/province"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shipping_postal_code"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Shipping postal code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "shipping_country"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Shipping country"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_activity_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date of the last activity on the account"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_viewed_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when the account was last viewed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_referenced_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when the account was last referenced"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_deleted"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the account has been deleted"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_customer_portal"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether this account has customer portal access"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_person_account"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether this is a person account"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "jigsaw"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Data.com ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "clean_status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Clean status from Data.com"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "account_source"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Source of the account"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sic_desc"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "SIC description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "duns_number"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "D-U-N-S number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tradestyle"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Tradestyle"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "naics_code"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "NAICS code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "naics_desc"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "NAICS description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "year_started"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Year the account was started"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Additional metadata about the account"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SalesforceContactEntity",
      children: [jsx(_components.p, {
        children: "Schema for Salesforce Contact entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_contact.htm",
          children: "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_contact.htm"
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
              children: "Contact's first name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's last name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's phone number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mobile_phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's mobile phone number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fax"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's fax number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "title"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's job title"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "department"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact's department"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "account_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the associated account"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "lead_source"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Source of the lead"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "birthdate"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Contact's birthdate"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user who owns the contact"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_activity_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date of the last activity on the contact"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_viewed_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when the contact was last viewed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_referenced_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when the contact was last referenced"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_deleted"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the contact has been deleted"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_email_bounced"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether emails to this contact bounce"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_unread_by_owner"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the contact is unread by the owner"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "jigsaw"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Data.com ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "jigsaw_contact_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Data.com contact ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "clean_status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Clean status from Data.com"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "level"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Contact level"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "languages"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Languages spoken"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_opted_out_of_email"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the contact has opted out of email"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_opted_out_of_fax"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the contact has opted out of fax"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "do_not_call"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the contact should not be called"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mailing_street"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Mailing street address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mailing_city"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Mailing city"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mailing_state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Mailing state/province"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mailing_postal_code"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Mailing postal code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "mailing_country"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Mailing country"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "other_street"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Other street address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "other_city"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Other city"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "other_state"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Other state/province"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "other_postal_code"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Other postal code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "other_country"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Other country"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assistant_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Assistant's name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assistant_phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Assistant's phone number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reports_to_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the contact this contact reports to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email_bounced_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when email bounced"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email_bounced_reason"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Reason why email bounced"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "individual_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the associated individual"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Additional metadata about the contact"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "SalesforceOpportunityEntity",
      children: [jsx(_components.p, {
        children: "Schema for Salesforce Opportunity entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_opportunity.htm",
          children: "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_opportunity.htm"
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
              children: "account_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the associated account"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Opportunity amount"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "close_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Expected close date"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "stage_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Sales stage"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "probability"
            }), jsx(_components.td, {
              children: "Optional[float]"
            }), jsx(_components.td, {
              children: "Probability percentage"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "forecast_category"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Forecast category"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "forecast_category_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Forecast category name"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "campaign_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the associated campaign"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_opportunity_line_item"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the opportunity has line items"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pricebook2_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the associated pricebook"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the user who owns the opportunity"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_activity_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date of the last activity on the opportunity"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_viewed_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when the opportunity was last viewed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_referenced_date"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Date when the opportunity was last referenced"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_deleted"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the opportunity has been deleted"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_won"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the opportunity is won"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_closed"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the opportunity is closed"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_open_activity"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the opportunity has open activities"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_overdue_task"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates whether the opportunity has overdue tasks"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Opportunity description"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Opportunity type"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "lead_source"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Source of the lead"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "next_step"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Next step in the sales process"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Additional metadata about the opportunity"
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
