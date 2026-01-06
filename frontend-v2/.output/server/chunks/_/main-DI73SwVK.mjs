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
        alt: "Outlook Calendar logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Outlook Calendar"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Outlook Calendar source connector integrates with the Microsoft Graph API to extract data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from Outlook calendars."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to calendars, events, and attachments\nwith proper timezone handling and meeting management features."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/outlook_calendar.py",
      children: jsx(_components.p, {
        children: "Explore the Outlook Calendar connector implementation"
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
      title: "OutlookCalendarCalendarEntity",
      children: [jsx(_components.p, {
        children: "Schema for an Outlook Calendar object."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0"
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
              children: "color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Color theme to distinguish the calendar (auto, lightBlue, etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "hex_color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Calendar color in hex format (e.g., #FF0000)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "change_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Version identifier that changes when the calendar is modified."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "can_edit"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user can write to the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "can_share"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user can share the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "can_view_private_items"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user can view private events in the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_default_calendar"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this is the default calendar for new events."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_removable"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this calendar can be deleted from the mailbox."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_tallying_responses"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this calendar supports tracking meeting responses."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "owner"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the calendar owner (name and email)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "allowed_online_meeting_providers"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Online meeting providers that can be used (teamsForBusiness, etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "default_online_meeting_provider"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Default online meeting provider for this calendar."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OutlookCalendarEventEntity",
      children: [jsx(_components.p, {
        children: "Schema for an Outlook Calendar Event object."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0"
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
              children: "The subject/title of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body_preview"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Preview of the event body content."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body_content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Full body content of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "body_content_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Content type of the body (html or text)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_datetime"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Start date and time of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Timezone for the start time."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "end_datetime"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "End date and time of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "end_timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Timezone for the end time."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_all_day"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the event lasts all day."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_cancelled"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the event has been cancelled."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_draft"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the event is a draft."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_online_meeting"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether this is an online meeting."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_organizer"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the user is the organizer."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_reminder_on"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether a reminder is set."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "show_as"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "How to show time (free, busy, tentative, oof, etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "importance"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Importance level (low, normal, high)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "sensitivity"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Sensitivity level (normal, personal, private, confidential)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "response_status"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Response status of the user to the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organizer"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Event organizer information (name and email)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attendees"
            }), jsx(_components.td, {
              children: "Optional[List[Dict[str, Any]]]"
            }), jsx(_components.td, {
              children: "List of event attendees with their response status."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "location"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Primary location information for the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "locations"
            }), jsx(_components.td, {
              children: "List[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "List of all locations associated with the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "categories"
            }), jsx(_components.td, {
              children: "List[str]"
            }), jsx(_components.td, {
              children: "Categories assigned to the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to open the event in Outlook on the web."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "online_meeting_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to join the online meeting."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "online_meeting_provider"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Online meeting provider (teamsForBusiness, etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "online_meeting"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Online meeting details and join information."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "series_master_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the master event if this is part of a recurring series."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "recurrence"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Recurrence pattern for recurring events."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "reminder_minutes_before_start"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Minutes before start time when reminder fires."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "has_attachments"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the event has attachments."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "ical_uid"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Unique identifier across calendars."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "change_key"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Version identifier that changes when event is modified."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "original_start_timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Start timezone when event was originally created."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "original_end_timezone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "End timezone when event was originally created."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "allow_new_time_proposals"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether invitees can propose new meeting times."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "hide_attendees"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether attendees are hidden from each other."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "OutlookCalendarAttachmentEntity",
      children: [jsx(_components.p, {
        children: "Schema for Outlook Calendar Event attachments."
      }), jsx(_components.p, {
        children: "Represents files attached to calendar events."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/attachment?view=graph-rest-1.0",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/attachment?view=graph-rest-1.0"
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
              children: "event_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the event this attachment belongs to"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attachment_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Microsoft Graph attachment ID"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "MIME type of the attachment"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "is_inline"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the attachment is inline"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "content_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Content ID for inline attachments"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_at"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "When the attachment was last modified"
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
