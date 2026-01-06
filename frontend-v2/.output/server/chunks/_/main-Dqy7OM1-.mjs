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
        alt: "Excel logo",
        width: "48",
        height: "48",
        className: "connector-icon"
      }), jsx("h1", {
        style: {
          margin: 0
        },
        children: "Excel"
      })]
    }), "\n", jsx(_components.h2, {
      children: "Configuration"
    }), "\n", jsx(_components.p, {
      children: "Microsoft Excel source connector integrates with the Microsoft Graph API."
    }), "\n", jsx(_components.p, {
      children: "Synchronizes data from Microsoft Excel including workbooks, worksheets, and tables."
    }), "\n", jsx(_components.p, {
      children: "It provides comprehensive access to Excel resources with proper token refresh\nand rate limiting."
    }), "\n", jsx(Card, {
      title: "View Source Code",
      icon: "brands github",
      href: "https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/excel.py",
      children: jsx(_components.p, {
        children: "Explore the Excel connector implementation"
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
      title: "ExcelWorkbookEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Excel workbook (file)."
      }), jsx(_components.p, {
        children: "Represents the Excel file itself with metadata."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/driveitem",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/driveitem"
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
              children: "file_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "The full file name including extension."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "web_url"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "URL to open the workbook in Excel Online."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "size"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Size of the file in bytes."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "created_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who created the workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_by"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Identity of the user who last modified the workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "parent_reference"
            }), jsx(_components.td, {
              children: "Optional[Dict[str, Any]]"
            }), jsx(_components.td, {
              children: "Information about the parent folder/drive location."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "drive_id"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "ID of the drive containing this workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "description"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Description of the workbook if available."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ExcelWorksheetEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Excel worksheet (sheet/tab)."
      }), jsx(_components.p, {
        children: "Represents individual sheets within an Excel workbook."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/worksheet",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/worksheet"
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
              children: "workbook_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the parent workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workbook_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the parent workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "position"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "The zero-based position of the worksheet within the workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "visibility"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The visibility of the worksheet (Visible, Hidden, VeryHidden)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "range_address"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The address of the used range (e.g., 'A1:Z100')."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "cell_content"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Formatted text representation of the cell content in the used range."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "row_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of rows with data in the worksheet."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "column_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of columns with data in the worksheet."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_datetime"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Timestamp at which the worksheet was last modified."
            })]
          })]
        })]
      })]
    }), "\n", jsxs(Accordion, {
      title: "ExcelTableEntity",
      children: [jsx(_components.p, {
        children: "Schema for a Microsoft Excel table."
      }), jsx(_components.p, {
        children: "Represents structured data tables within worksheets."
      }), jsxs(_components.p, {
        children: ["Reference:\n", jsx(_components.a, {
          href: "https://learn.microsoft.com/en-us/graph/api/resources/table",
          children: "https://learn.microsoft.com/en-us/graph/api/resources/table"
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
              children: "workbook_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the parent workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "workbook_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the parent workbook."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "worksheet_id"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "ID of the parent worksheet."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "worksheet_name"
            }), jsx(_components.td, {
              children: "str"
            }), jsx(_components.td, {
              children: "Name of the parent worksheet."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "display_name"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Display name of the table."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "show_headers"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the header row is visible."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "show_totals"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the total row is visible."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "style"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "Style name of the table."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "highlight_first_column"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the first column contains special formatting."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "highlight_last_column"
            }), jsx(_components.td, {
              children: "Optional[bool]"
            }), jsx(_components.td, {
              children: "Indicates whether the last column contains special formatting."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "row_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of rows in the table."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "column_count"
            }), jsx(_components.td, {
              children: "Optional[int]"
            }), jsx(_components.td, {
              children: "Number of columns in the table."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "column_names"
            }), jsx(_components.td, {
              children: "Optional[List[str]]"
            }), jsx(_components.td, {
              children: "Names of the columns in the table."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "table_data"
            }), jsx(_components.td, {
              children: "Optional[str]"
            }), jsx(_components.td, {
              children: "The actual table data as formatted text (rows and columns)."
            })]
          }), jsxs(_components.tr, {
            children: [jsx(_components.td, {
              children: "last_modified_datetime"
            }), jsx(_components.td, {
              children: "Optional[Any]"
            }), jsx(_components.td, {
              children: "Timestamp at which the table was last modified."
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
