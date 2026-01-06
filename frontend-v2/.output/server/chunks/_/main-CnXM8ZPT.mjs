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
        alt: "Stripe logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Stripe"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Stripe source connector integrates with the Stripe API to extract payment and financial data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes comprehensive data from your Stripe account."
    }), "\n", jsx(_components.p, {
      children: "It provides access to all major Stripe resources\nincluding transactions, customers, subscriptions, and account analytics."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/stripe.py",
      children: jsx(_components.p, {
        children: "Explore the Stripe connector implementation"
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
        children: "Stripe authentication credentials schema."
      }), jsx(ParamField, {
        path: "api_key",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "The API key for the Stripe account. Should start with 'sk_test_' for test mode or 'sk_live_' for live mode."
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Configuration Options"
    }), "\n", jsx(_components.p, {
      children: "This connector does not have any additional configuration options."
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "StripeBalanceEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Balance resource."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/balance/balance_object",
          children: "https://stripe.com/docs/api/balance/balance_object"
        })
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
              children: "available"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Funds that are available to be paid out, broken down by currency"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pending"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Funds not yet available, broken down by currency"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "instant_available"
            }), jsx(_components.td, {
              children: "Optional[List[Dict[str, Any]]]"
            }), jsx(_components.td, {
              children: "Funds available for Instant Payouts (if enabled)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "connect_reserved"
            }), jsx(_components.td, {
              children: "Optional[List[Dict[str, Any]]]"
            }), jsx(_components.td, {
              children: "Funds reserved for connected accounts (if using Connect)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "livemode"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this balance is in live mode (vs test mode)"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeBalanceTransactionEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Balance Transaction resource."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/balance_transactions",
          children: "https://stripe.com/docs/api/balance_transactions"
        })
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
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Gross amount of the transaction, in cents"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Three-letter ISO currency code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Text description of the transaction"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fee"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Fees (in cents) taken from this transaction"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "fee_details"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Detailed breakdown of fees (type, amount, application, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "net"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Net amount of the transaction, in cents"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reporting_category"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Reporting category (e.g., 'charge', 'refund', etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "source"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the charge or other object that caused this balance transaction"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the balance transaction (e.g., 'available', 'pending')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Transaction type (e.g., 'charge', 'refund', 'payout')"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeChargeEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Charge entities."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/charges",
          children: "https://stripe.com/docs/api/charges"
        })
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
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Amount charged in cents"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Three-letter ISO currency code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "captured"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the charge was captured"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "paid"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the charge was paid"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "refunded"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the charge was refunded"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Arbitrary description of the charge"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "receipt_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view this charge's receipt"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "customer_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the Customer this charge belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "invoice_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the Invoice this charge is linked to (if any)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs attached to the charge"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeCustomerEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Customer entities."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/customers",
          children: "https://stripe.com/docs/api/customers"
        })
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
              children: "email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The customer's email address"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The customer's phone number"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Arbitrary description of the customer"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Preferred currency for the customer's recurring payments"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "default_source"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the default payment source (e.g. card) attached to this customer"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "delinquent"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the customer has any unpaid/overdue invoices"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "invoice_prefix"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Prefix for the customer's invoices"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs attached to the customer"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeEventEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Event resource."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/events",
          children: "https://stripe.com/docs/api/events"
        })
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
              children: "event_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The event's type (e.g., 'charge.succeeded', 'customer.created')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "api_version"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "API version used to render event data"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "data"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "The event payload. Typically includes 'object' and 'previous_attributes'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "livemode"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the event was triggered in live mode"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "pending_webhooks"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of webhooks yet to be delivered"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "request"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information on the request that created or triggered the event"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeInvoiceEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Invoice entities."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/invoices",
          children: "https://stripe.com/docs/api/invoices"
        })
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
              children: "customer_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The ID of the customer this invoice belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "number"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "A unique, user-facing reference for this invoice"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Invoice status (e.g., 'draft', 'open', 'paid', 'void')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "amount_due"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Final amount due in cents (before any payment or credit)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "amount_paid"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Amount paid in cents"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "amount_remaining"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Amount remaining to be paid in cents"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "due_date"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Date on which payment is due (if applicable)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "paid"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the invoice has been fully paid"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Three-letter ISO currency code (e.g. 'usd')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs that can be attached to the invoice"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripePaymentIntentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe PaymentIntent entities."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/payment_intents",
          children: "https://stripe.com/docs/api/payment_intents"
        })
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
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Amount in cents intended to be collected by this PaymentIntent"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Three-letter ISO currency code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the PaymentIntent (e.g. 'requires_payment_method', 'succeeded')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Arbitrary description for the PaymentIntent"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "customer_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the Customer this PaymentIntent is for (if any)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs attached to the PaymentIntent"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripePaymentMethodEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe PaymentMethod resource."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/payment_methods",
          children: "https://stripe.com/docs/api/payment_methods"
        })
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
              children: "type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of the PaymentMethod (card, ideal, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "billing_details"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Billing information associated with the PaymentMethod"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "customer_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the Customer to which this PaymentMethod is saved (if any)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "card"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "If the PaymentMethod type is 'card', details about the card (brand, last4, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs that can be attached to the PaymentMethod"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripePayoutEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Payout resource."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/payouts",
          children: "https://stripe.com/docs/api/payouts"
        })
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
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Amount in cents to be transferred"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Three-letter ISO currency code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "arrival_date"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Date the payout is expected to arrive in the bank"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "An arbitrary string attached to the payout"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "destination"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the bank account or card the payout was sent to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "method"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The method used to send this payout (e.g., 'standard', 'instant')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the payout (e.g., 'paid', 'pending', 'in_transit')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "statement_descriptor"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Extra information to be displayed on the user's bank statement"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs that can be attached to the payout"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeRefundEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Refund resource."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/refunds",
          children: "https://stripe.com/docs/api/refunds"
        })
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
              children: "amount"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Amount in cents refunded"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "currency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Three-letter ISO currency code"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the refund (e.g., 'pending', 'succeeded', 'failed')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reason"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Reason for the refund (duplicate, fraudulent, requested_by_customer, etc.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "receipt_number"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Transaction number that appears on email receipts issued for this refund"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "charge_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the charge being refunded"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "payment_intent_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the PaymentIntent being refunded (if applicable)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs that can be attached to the refund"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "StripeSubscriptionEntity",
      children: [jsx(_components.p, {
        children: "Schema for Stripe Subscription entities."
      }), jsx(_components.p, {
        children: jsx(_components.a, {
          href: "https://stripe.com/docs/api/subscriptions",
          children: "https://stripe.com/docs/api/subscriptions"
        })
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
              children: "customer_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The ID of the customer who owns this subscription"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the subscription (e.g., 'active', 'past_due', 'canceled')"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "current_period_start"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Start of the current billing period for this subscription"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "current_period_end"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "End of the current billing period for this subscription"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "cancel_at_period_end"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the subscription will cancel at the end of the current period"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "canceled_at"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "When the subscription was canceled (if any)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "metadata"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Set of key-value pairs attached to the subscription"
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
