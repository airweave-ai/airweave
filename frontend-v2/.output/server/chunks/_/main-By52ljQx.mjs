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
    code: "code",
    h2: "h2",
    h3: "h3",
    li: "li",
    ol: "ol",
    p: "p",
    pre: "pre",
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
  }, { Accordion, AccordionGroup, Card, CodeBlock, Note, ParamField, Warning } = _components;
  if (!Accordion) _missingMdxReference("Accordion");
  if (!AccordionGroup) _missingMdxReference("AccordionGroup");
  if (!Card) _missingMdxReference("Card");
  if (!CodeBlock) _missingMdxReference("CodeBlock");
  if (!Note) _missingMdxReference("Note");
  if (!ParamField) _missingMdxReference("ParamField");
  if (!Warning) _missingMdxReference("Warning");
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
        alt: "Zendesk logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Zendesk"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Zendesk source connector integrates with the Zendesk API to extract and synchronize data."
    }), "\n", jsx(_components.p, {
      children: "Connects to your Zendesk instance to sync tickets, comments, users, orgs, and attachments."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/zendesk.py",
      children: jsx(_components.p, {
        children: "Explore the Zendesk connector implementation"
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
        children: "Zendesk configuration schema."
      }), jsx(ParamField, {
        path: "subdomain",
        type: "str",
        required: true,
        children: jsx(_components.p, {
          children: "Your Zendesk subdomain only (e.g., 'mycompany' NOT 'mycompany.zendesk.com')"
        })
      }), jsx(ParamField, {
        path: "exclude_closed_tickets",
        type: "Optional[bool]",
        required: false,
        default: false,
        children: jsx(_components.p, {
          children: "Skip closed tickets during sync (recommended for faster syncing)"
        })
      })]
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "ZendeskTicketEntity",
      children: [jsx(_components.p, {
        children: "Schema for Zendesk ticket entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/",
          children: "https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/"
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
              children: "ticket_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Unique identifier of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "subject"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The subject of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The description of the ticket (first comment)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "requester_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the user who requested the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "requester_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the user who requested the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "requester_email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Email of the user who requested the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the user assigned to the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the user assigned to the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "assignee_email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Email of the user assigned to the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "status"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Current status of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "priority"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Priority level of the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Tags associated with the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_fields"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Custom field values for the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organization_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the organization associated with the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organization_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the organization associated with the ticket"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "group_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the group the ticket belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "group_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the group the ticket belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ticket_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Type of the ticket (question, incident, problem, task)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to view the ticket in Zendesk"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ZendeskCommentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Zendesk comment entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-comments/",
          children: "https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-comments/"
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
              children: "comment_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Unique identifier of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ticket_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "ID of the ticket this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ticket_subject"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Subject of the ticket this comment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "ID of the user who wrote the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the user who wrote the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "author_email"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Email of the user who wrote the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The content of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "html_body"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "HTML formatted content of the comment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "public"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the comment is public or internal"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attachments"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Attachments associated with this comment"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ZendeskUserEntity",
      children: [jsx(_components.p, {
        children: "Schema for Zendesk user entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.zendesk.com/api-reference/ticketing/users/users/",
          children: "https://developer.zendesk.com/api-reference/ticketing/users/users/"
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
              children: "user_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Unique identifier of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "email"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Email address of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "role"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Role of the user (end-user, agent, admin)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "active"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user account is active"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_login_at"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "When the user last logged in"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organization_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the organization the user belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organization_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Name of the organization the user belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "phone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Phone number of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "time_zone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Time zone of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "locale"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Locale of the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_fields"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Custom field values for the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Tags associated with the user"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "user_fields"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "User-specific custom fields"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ZendeskOrganizationEntity",
      children: [jsx(_components.p, {
        children: "Schema for Zendesk organization entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/",
          children: "https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/"
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
              children: "organization_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Unique identifier of the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "domain_names"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Domain names associated with the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "details"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Details about the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "notes"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Notes about the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "tags"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Tags associated with the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "custom_fields"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Custom field values for the organization"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organization_fields"
            }), jsx(_components.td, {
              children: "Dict[str, Any]"
            }), jsx(_components.td, {
              children: "Organization-specific custom fields"
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ZendeskAttachmentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Zendesk attachment entities."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-attachments/",
          children: "https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-attachments/"
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
              children: "attachment_id"
            }), jsx(_components.td, {
              children: "int"
            }), jsx(_components.td, {
              children: "Unique identifier of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ticket_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the ticket this attachment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "comment_id"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "ID of the comment this attachment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ticket_subject"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Subject of the ticket this attachment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_type"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "MIME type of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "file_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Original filename of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "thumbnails"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Thumbnail information for the attachment"
            })]
          })]
        })]
      })]
    }), "\n", "\n", jsx(_components.h2, {
      children: "Setting Up Your Zendesk OAuth Application"
    }), "\n", jsx(_components.p, {
      children: "Zendesk requires you to create your own OAuth application (BYOC - Bring Your Own Credentials) to connect with Airweave. Follow these steps to set up your OAuth client:"
    }), "\n", jsx(_components.h3, {
      children: "Step 1: Create OAuth Client in Zendesk"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "Log into your Zendesk Admin Center"
      }), "\n", jsxs(_components.li, {
        children: ["Navigate to ", jsx(_components.strong, {
          children: "Apps and integrations"
        }), " → ", jsx(_components.strong, {
          children: "APIs"
        }), " → ", jsx(_components.strong, {
          children: "OAuth clients"
        })]
      }), "\n", jsxs(_components.li, {
        children: ["Click ", jsx(_components.strong, {
          children: "Add OAuth client"
        }), " on the right side"]
      }), "\n"]
    }), "\n", jsx(_components.h3, {
      children: "Step 2: Configure OAuth Client"
    }), "\n", jsx(_components.p, {
      children: "Fill out the OAuth client form with the following details:"
    }), "\n", jsxs(ParamField, {
      path: "Name",
      type: "string",
      required: true,
      children: [jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Example:"
        }), " ", jsx(_components.code, {
          children: "Airweave"
        })]
      }), jsx(_components.p, {
        children: "This name will be shown to users during the authorization flow."
      })]
    }), "\n", jsxs(ParamField, {
      path: "Description",
      type: "string",
      required: false,
      children: [jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Example:"
        }), " ", jsx(_components.code, {
          children: "Airweave connector for syncing Zendesk data"
        })]
      }), jsx(_components.p, {
        children: "Optional description visible during authorization."
      })]
    }), "\n", jsxs(ParamField, {
      path: "Company",
      type: "string",
      required: false,
      children: [jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Example:"
        }), " ", jsx(_components.code, {
          children: "Your Company Name"
        })]
      }), jsx(_components.p, {
        children: "Helps users understand who they're granting access to."
      })]
    }), "\n", jsxs(ParamField, {
      path: "Identifier",
      type: "string",
      required: true,
      children: [jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Example:"
        }), " ", jsx(_components.code, {
          children: "airweave"
        })]
      }), jsxs(_components.p, {
        children: ["This becomes your ", jsx(_components.strong, {
          children: "Client ID"
        }), ". You can use the auto-generated value or customize it."]
      })]
    }), "\n", jsxs(ParamField, {
      path: "Type client",
      type: "enum",
      required: true,
      children: [jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Must be:"
        }), " ", jsx(_components.code, {
          children: "Confidential"
        })]
      }), jsx(Warning, {
        children: jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Important:"
          }), ' Select "Confidential", not "Public". Public clients will not work with Airweave.']
        })
      })]
    }), "\n", jsxs(ParamField, {
      path: "Redirect URLs",
      type: "string",
      required: true,
      children: [jsx(_components.p, {
        children: "Enter your Airweave callback URL. Use the appropriate URL for your environment:"
      }), jsxs(_components.ul, {
        children: ["\n", jsxs(_components.li, {
          children: [jsx(_components.strong, {
            children: "Production:"
          }), " ", jsx(_components.code, {
            children: "https://api.airweave.ai/source-connections/callback"
          })]
        }), "\n", jsxs(_components.li, {
          children: [jsx(_components.strong, {
            children: "Local:"
          }), " ", jsx(_components.code, {
            children: "http://localhost:8001/source-connections/callback"
          })]
        }), "\n"]
      }), jsx(Note, {
        children: jsxs(_components.p, {
          children: ["The redirect URL must match exactly (including protocol and trailing slashes). For localhost, ", jsx(_components.code, {
            children: "http://"
          }), " is required."]
        })
      })]
    }), "\n", jsx(_components.h3, {
      children: "Step 3: Save and Generate Secret"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: ["Click ", jsx(_components.strong, {
          children: "Save"
        })]
      }), "\n", jsxs(_components.li, {
        children: ["After saving, a ", jsx(_components.strong, {
          children: "Secret"
        }), " field will appear with your client secret"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Copy the entire secret"
        }), " immediately - it will only be shown once in full"]
      }), "\n", jsxs(_components.li, {
        children: ["Click ", jsx(_components.strong, {
          children: "Save"
        }), " again to finalize"]
      }), "\n"]
    }), "\n", jsx(Warning, {
      children: jsxs(_components.p, {
        children: [jsx(_components.strong, {
          children: "Security Note:"
        }), " The client secret will only be displayed fully once. After clicking Save, you'll only see the first 9 characters. Store it securely!"]
      })
    }), "\n", jsx(_components.h3, {
      children: "Step 4: Activate the OAuth Client"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsx(_components.li, {
        children: "Find your OAuth client in the OAuth clients list"
      }), "\n", jsxs(_components.li, {
        children: ["Change the ", jsx(_components.strong, {
          children: "Status"
        }), " from ", jsx(_components.strong, {
          children: "Inactive"
        }), " to ", jsx(_components.strong, {
          children: "Active"
        })]
      }), "\n", jsx(_components.li, {
        children: "Save the changes"
      }), "\n"]
    }), "\n", jsx(Note, {
      children: jsx(_components.p, {
        children: `The OAuth client must be in "Active" status to accept authorization requests. If it's inactive, you'll receive an "Invalid Authorization Request" error.`
      })
    }), "\n", jsx(_components.h3, {
      children: "Step 5: Configure in Airweave"
    }), "\n", jsx(_components.p, {
      children: "When creating a Zendesk connection in Airweave, you'll need to provide:"
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Subdomain:"
        }), " Your Zendesk subdomain only (e.g., ", jsx(_components.code, {
          children: "mycompany"
        }), " NOT ", jsx(_components.code, {
          children: "mycompany.zendesk.com"
        }), ")"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Client ID:"
        }), " The identifier you set in Step 2"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.strong, {
          children: "Client Secret:"
        }), " The secret you copied in Step 3"]
      }), "\n"]
    }), "\n", jsx(CodeBlock, {
      title: "Example Configuration",
      children: jsx(_components.pre, {
        children: jsx(_components.code, {
          className: "language-json",
          children: '{\n  "config": {\n    "subdomain": "mycompany"\n  },\n  "authentication": {\n    "client_id": "airweave",\n    "client_secret": "your-secret-here"\n  }\n}\n'
        })
      })
    }), "\n", jsx(_components.h2, {
      children: "Troubleshooting"
    }), "\n", jsxs(AccordionGroup, {
      children: [jsxs(Accordion, {
        title: "Invalid Authorization Request Error",
        children: [jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Cause:"
          }), " Your OAuth client is inactive or misconfigured."]
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Solution:"
          })
        }), jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: 'Verify the OAuth client status is "Active"'
          }), "\n", jsx(_components.li, {
            children: 'Ensure the client type is set to "Confidential"'
          }), "\n", jsx(_components.li, {
            children: "Check that the redirect URL exactly matches your Airweave callback URL"
          }), "\n"]
        })]
      }), jsxs(Accordion, {
        title: "Client Secret Not Working",
        children: [jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Cause:"
          }), " Incomplete secret copied or secret regenerated."]
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Solution:"
          })
        }), jsxs(_components.ul, {
          children: ["\n", jsx(_components.li, {
            children: "Make sure you copied the entire secret (it may extend past the visible text box)"
          }), "\n", jsx(_components.li, {
            children: 'If needed, click the "Regenerate" button to generate a new secret'
          }), "\n", jsx(_components.li, {
            children: "Copy the new secret immediately and update it in Airweave"
          }), "\n"]
        })]
      }), jsxs(Accordion, {
        title: "Redirect URI Mismatch",
        children: [jsxs(_components.p, {
          children: [jsx(_components.strong, {
            children: "Cause:"
          }), " The redirect URL in your OAuth client doesn't match Airweave's callback URL."]
        }), jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Solution:"
          })
        }), jsxs(_components.ul, {
          children: ["\n", jsxs(_components.li, {
            children: ["Verify the redirect URL is exactly: ", jsx(_components.code, {
              children: "https://api.airweave.ai/source-connections/callback"
            })]
          }), "\n", jsx(_components.li, {
            children: "Check for trailing slashes, protocol (http/https), and exact domain match"
          }), "\n", jsxs(_components.li, {
            children: ["For local development, ensure you're using ", jsx(_components.code, {
              children: "http://"
            }), " not ", jsx(_components.code, {
              children: "https://"
            })]
          }), "\n"]
        })]
      })]
    }), "\n", jsx(_components.h2, {
      children: "Required Scopes"
    }), "\n", jsx(_components.p, {
      children: "Airweave requires the following Zendesk OAuth scopes:"
    }), "\n", jsxs(_components.ul, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "read"
        }), " - Read access to tickets, users, organizations, and comments"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.code, {
          children: "write"
        }), " - Write access for updating ticket data (optional, for future features)"]
      }), "\n"]
    }), "\n", jsx(_components.p, {
      children: "These scopes are automatically included in the authorization request."
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
