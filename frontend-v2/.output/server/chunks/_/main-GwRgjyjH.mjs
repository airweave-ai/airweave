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
        alt: "Google Calendar logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Google Calendar"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Google Calendar source connector integrates with the Google Calendar API to extract data."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes calendars, events, and free/busy information."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to your\nGoogle Calendar scheduling information for productivity and time management insights."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/google_calendar.py",
      children: jsx(_components.p, {
        children: "Explore the Google Calendar connector implementation"
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
      children: "This connector does not have any additional configuration options."
    }), "\n", jsx(_components.h2, {
      children: "Data Models"
    }), "\n", jsx(_components.p, {
      children: "The following data models are available for this connector:"
    }), "\n", jsxs(Accordion, {
      title: "GoogleCalendarCalendarEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Google Calendar object (the underlying calendar resource)."
      }), jsxs(_components.p, {
        children: ["See: ", jsx(_components.a, {
          href: "https://developers.google.com/calendar/api/v3/reference/calendars",
          children: "https://developers.google.com/calendar/api/v3/reference/calendars"
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
              children: "summary"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "location"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Geographic location of the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "time_zone"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The time zone of the calendar."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GoogleCalendarListEntity",
      children: [jsx(_components.p, {
        children: "Schema for a CalendarList entry, i.e., how the user sees a calendar."
      }), jsxs(_components.p, {
        children: ["See: ", jsx(_components.a, {
          href: "https://developers.google.com/calendar/api/v3/reference/calendarList",
          children: "https://developers.google.com/calendar/api/v3/reference/calendarList"
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
              children: "summary"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "summary_override"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "User-defined name for the calendar, if set."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "color_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Color ID reference for the calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "background_color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Background color in HEX."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "foreground_color"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Foreground color in HEX."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "hidden"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Whether the calendar is hidden from the UI."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "selected"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Indicates if the calendar is selected in the UI."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "access_role"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The effective access role that the authenticated user has on the calendar. E.g., 'owner', 'reader', 'writer'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "primary"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Flag to indicate if this is the primary calendar."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "deleted"
            }), jsx(_components.td, {
              children: "bool"
            }), jsx(_components.td, {
              children: "Flag to indicate if this calendar has been deleted."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GoogleCalendarEventEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Google Calendar Event."
      }), jsxs(_components.p, {
        children: ["See: ", jsx(_components.a, {
          href: "https://developers.google.com/calendar/api/v3/reference/events",
          children: "https://developers.google.com/calendar/api/v3/reference/events"
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
              children: "status"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Status of the event (e.g., 'confirmed')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "html_link"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "An absolute link to the event in the Google Calendar UI."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "summary"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Title of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "location"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Geographic location of the event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "color_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Color ID for this event."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_datetime"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "Start datetime if the event has a specific datetime. (DateTime from 'start' if 'dateTime' is present.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "start_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Start date if the event is an all-day event. (Date from 'start' if 'date' is present.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "end_datetime"
            }), jsx(_components.td, {
              children: "Optional[datetime]"
            }), jsx(_components.td, {
              children: "End datetime if the event has a specific datetime. (DateTime from 'end' if 'dateTime' is present.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "end_date"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "End date if the event is an all-day event. (Date from 'end' if 'date' is present.)"
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "recurrence"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "recurring_event_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "For recurring events, identifies the event ID of the recurring series."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "organizer"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The organizer of the event. Usually contains 'email' and 'displayName'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "creator"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "The creator of the event. Usually contains 'email' and 'displayName'."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "attendees"
            }), jsx(_components.td, {
              children: "Optional[List[Dict[str, Any]]]"
            }), jsx(_components.td, {
              children: "The attendees of the event (each dict typically has 'email', 'responseStatus', etc.)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "transparency"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Specifies whether the event blocks time on the calendar ('opaque') or not ('transparent')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "visibility"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Visibility of the event (e.g., 'default', 'public')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "conference_data"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Conference data associated with the event, e.g., hangout or meet link."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "event_type"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Event type. E.g., 'default' or 'focus'."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "GoogleCalendarFreeBusyEntity",
      children: [jsx(_components.p, {
        children: "Schema for a FreeBusy response entity for a given calendar."
      }), jsxs(_components.p, {
        children: ["See: ", jsx(_components.a, {
          href: "https://developers.google.com/calendar/api/v3/reference/freebusy",
          children: "https://developers.google.com/calendar/api/v3/reference/freebusy"
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
              children: "calendar_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the calendar for which free/busy is returned."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "busy"
            }), jsx(_components.td, {
              children: "List[Dict[str, str]]"
            }), jsx(_components.td, {
              children: "List of time ranges during which this calendar is busy."
            })]
          })]
        })]
      })]
    }), "\n", "\n", jsx(_components.h2, {
      children: "Integrate Airweave with Google APIs on localhost"
    }), "\n", jsxs(_components.p, {
      children: ["This guide will walk you through connecting Google Workspace APIs to Airweave when running locally.\nGoogle provides extensive ", jsx(_components.a, {
        href: "https://developers.google.com/workspace/guides/get-started",
        children: "documentation"
      }), " on setting up your workspace.\nBelow is a streamlined process for connecting Google APIs to Airweave."]
    }), "\n", jsxs(_components.ol, {
      children: ["\n", jsxs(_components.li, {
        children: [jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/create-project",
          children: "Create a Google Cloud project"
        }), " for your Google Workspace (if you don't already have one)"]
      }), "\n", jsxs(_components.li, {
        children: [jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/enable-apis",
          children: "Enable the Google Workspace APIs"
        }), " for Gmail, Google Calendar, and Google Drive"]
      }), "\n", jsx(_components.li, {
        children: jsx(_components.a, {
          href: "https://developers.google.com/workspace/guides/configure-oauth-consent",
          children: "Configure Google OAuth 2.0 consent screen"
        })
      }), "\n", jsxs(_components.li, {
        children: ["Under ", jsx(_components.code, {
          children: "Audience"
        }), ", select ", jsx(_components.code, {
          children: "Make external"
        }), " and add test users"]
      }), "\n", jsxs(_components.li, {
        children: ["Under ", jsx(_components.code, {
          children: "Data Access"
        }), ", add the following scopes:"]
      }), "\n"]
    }), "\n", jsx(_components.pre, {
      children: jsx(_components.code, {
        children: "https://www.googleapis.com/auth/docs\nhttps://www.googleapis.com/auth/drive.photos.readonly\nhttps://www.googleapis.com/auth/drive\nhttps://www.googleapis.com/auth/drive.readonly\nhttps://www.googleapis.com/auth/drive.metadata\nhttps://www.googleapis.com/auth/drive.metadata.readonly\nhttps://www.googleapis.com/auth/gmail.readonly\nhttps://www.googleapis.com/auth/calendar.events.public.readonly\nhttps://www.googleapis.com/auth/calendar.freebusy\nhttps://www.googleapis.com/auth/calendar.readonly\nhttps://www.googleapis.com/auth/calendar.calendars.readonly\nhttps://www.googleapis.com/auth/calendar.events.owned.readonly\nhttps://www.googleapis.com/auth/calendar.events.readonly\n"
      })
    }), "\n", jsxs(_components.ol, {
      start: "6",
      children: ["\n", jsxs(_components.li, {
        children: ["\n", jsx(_components.p, {
          children: jsx(_components.a, {
            href: "https://developers.google.com/workspace/guides/create-credentials#oauth-client-id",
            children: "Create OAuth client ID credentials"
          })
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsx(_components.p, {
          children: 'Under "Authorized redirect URIs," click "+ Add URI" add the Redirect URI. Use the appropriate URL for your environment:'
        }), "\n", jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Production (Airweave Cloud):"
          })
        }), "\n", jsx(_components.pre, {
          children: jsx(_components.code, {
            children: "https://api.airweave.ai/source-connections/callback\n"
          })
        }), "\n", jsx(_components.p, {
          children: jsx(_components.strong, {
            children: "Local:"
          })
        }), "\n", jsx(_components.pre, {
          children: jsx(_components.code, {
            children: "http://localhost:8001/source-connections/callback\n"
          })
        }), "\n"]
      }), "\n", jsxs(_components.li, {
        children: ["\n", jsxs(_components.p, {
          children: ["Locate the client ID and client secret from your newly created OAuth client. Add these credentials to the ", jsx(_components.code, {
            children: "dev.integrations.yml"
          }), " file to enable Google API integration."]
        }), "\n"]
      }), "\n"]
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
