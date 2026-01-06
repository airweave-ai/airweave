import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import * as React from "react";
import { useState, createContext, useContext } from "react";
import { T as Tabs, a as TabsList, b as TabsTrigger, c as TabsContent } from "./tabs-ChSqzczQ.mjs";
import { a as cn } from "./router-BGxBdlkD.mjs";
const ApiFormContext = createContext(null);
function useApiFormContext() {
  const context = useContext(ApiFormContext);
  if (!context) {
    throw new Error("ApiForm compound components must be used within ApiForm");
  }
  return context;
}
const methodColors = {
  GET: "text-blue-400",
  POST: "text-emerald-400",
  PUT: "text-orange-400",
  DELETE: "text-red-400",
  PATCH: "text-yellow-400"
};
function ApiForm({
  method,
  endpoint,
  body,
  onBodyChange,
  defaultTab = "form",
  children,
  className
}) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  return /* @__PURE__ */ jsx(
    ApiFormContext.Provider,
    {
      value: {
        method,
        endpoint,
        body,
        onBodyChange,
        activeTab,
        setActiveTab
      },
      children: /* @__PURE__ */ jsx(
        Tabs,
        {
          value: activeTab,
          onValueChange: (value) => setActiveTab(value),
          className: cn("w-full", className),
          children
        }
      )
    }
  );
}
function Toggle({ className }) {
  return /* @__PURE__ */ jsxs(TabsList, { className: cn("w-full", className), children: [
    /* @__PURE__ */ jsx(TabsTrigger, { value: "form", className: "flex-1", children: "Form" }),
    /* @__PURE__ */ jsx(TabsTrigger, { value: "code", className: "flex-1", children: "Code" })
  ] });
}
function FormView({ children, className }) {
  return /* @__PURE__ */ jsx(TabsContent, { value: "form", className: cn("py-4", className), children });
}
function JsonValue({
  keyName,
  value,
  path,
  editable,
  onValueChange,
  indent
}) {
  const indentClass = `pl-${indent * 4}`;
  if (value === null) {
    return /* @__PURE__ */ jsxs("div", { className: indentClass, children: [
      /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
        '"',
        keyName,
        '"'
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": " }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-500", children: "null" })
    ] });
  }
  if (typeof value === "boolean") {
    return /* @__PURE__ */ jsxs("div", { className: cn("flex items-center", indentClass), children: [
      /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
        '"',
        keyName,
        '"'
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": " }),
      editable ? /* @__PURE__ */ jsx(
        "button",
        {
          type: "button",
          onClick: () => onValueChange(path, !value),
          className: "text-amber-400 underline underline-offset-2 hover:text-amber-300",
          children: value.toString()
        }
      ) : /* @__PURE__ */ jsx("span", { className: "text-amber-400", children: value.toString() })
    ] });
  }
  if (typeof value === "number") {
    return /* @__PURE__ */ jsxs("div", { className: cn("flex items-center", indentClass), children: [
      /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
        '"',
        keyName,
        '"'
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": " }),
      editable ? /* @__PURE__ */ jsx(
        "input",
        {
          type: "number",
          value,
          onChange: (e) => {
            const parsed = parseFloat(e.target.value);
            if (!isNaN(parsed)) {
              onValueChange(path, parsed);
            }
          },
          className: "w-20 rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-amber-400 focus:border-emerald-500 focus:outline-none"
        }
      ) : /* @__PURE__ */ jsx("span", { className: "text-amber-400", children: value })
    ] });
  }
  if (typeof value === "string") {
    return /* @__PURE__ */ jsxs("div", { className: cn("flex items-center", indentClass), children: [
      /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
        '"',
        keyName,
        '"'
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": " }),
      editable ? /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx("span", { className: "text-emerald-400", children: '"' }),
        /* @__PURE__ */ jsx(
          "input",
          {
            type: "text",
            value,
            onChange: (e) => onValueChange(path, e.target.value),
            className: "min-w-[60px] rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-emerald-400 focus:border-emerald-500 focus:outline-none",
            style: { width: `${Math.max(60, value.length * 8)}px` }
          }
        ),
        /* @__PURE__ */ jsx("span", { className: "text-emerald-400", children: '"' })
      ] }) : /* @__PURE__ */ jsxs("span", { className: "text-emerald-400", children: [
        '"',
        value,
        '"'
      ] })
    ] });
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return /* @__PURE__ */ jsxs("div", { className: indentClass, children: [
        /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
          '"',
          keyName,
          '"'
        ] }),
        /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": []" })
      ] });
    }
    return /* @__PURE__ */ jsxs("div", { className: indentClass, children: [
      /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
        '"',
        keyName,
        '"'
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": [" }),
      value.map((item, idx) => /* @__PURE__ */ jsx(
        JsonValue,
        {
          keyName: String(idx),
          value: item,
          path: [...path, String(idx)],
          editable,
          onValueChange,
          indent: indent + 1
        },
        idx
      )),
      /* @__PURE__ */ jsx("div", { className: indentClass, children: /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: "]" }) })
    ] });
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return /* @__PURE__ */ jsxs("div", { className: indentClass, children: [
        /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
          '"',
          keyName,
          '"'
        ] }),
        /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": {}" })
      ] });
    }
    return /* @__PURE__ */ jsxs("div", { className: indentClass, children: [
      /* @__PURE__ */ jsxs("span", { className: "text-sky-400", children: [
        '"',
        keyName,
        '"'
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: ": {" }),
      entries.map(([k, v], idx) => /* @__PURE__ */ jsxs(React.Fragment, { children: [
        /* @__PURE__ */ jsx(
          JsonValue,
          {
            keyName: k,
            value: v,
            path: [...path, k],
            editable,
            onValueChange,
            indent: indent + 1
          }
        ),
        idx < entries.length - 1 && /* @__PURE__ */ jsx("span", { className: "text-zinc-500", children: "," })
      ] }, k)),
      /* @__PURE__ */ jsx("div", { className: indentClass, children: /* @__PURE__ */ jsx("span", { className: "text-zinc-100", children: "}" }) })
    ] });
  }
  return null;
}
function CodeView({ editable = false, className }) {
  const { method, endpoint, body, onBodyChange } = useApiFormContext();
  const handleValueChange = (path, value) => {
    if (!onBodyChange) return;
    const newBody = { ...body };
    let current = newBody;
    for (let i = 0; i < path.length - 1; i++) {
      const key = path[i];
      if (typeof current[key] === "object" && current[key] !== null) {
        current[key] = Array.isArray(current[key]) ? [...current[key]] : { ...current[key] };
        current = current[key];
      }
    }
    const lastKey = path[path.length - 1];
    current[lastKey] = value;
    onBodyChange(newBody);
  };
  const entries = Object.entries(body);
  const hasBody = entries.length > 0;
  return /* @__PURE__ */ jsxs(TabsContent, { value: "code", className: cn("py-4", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "rounded-lg bg-zinc-950 p-4 font-mono text-sm", children: [
      /* @__PURE__ */ jsxs("div", { className: "mb-3 flex items-center gap-2", children: [
        /* @__PURE__ */ jsx("span", { className: cn("font-semibold", methodColors[method]), children: method }),
        /* @__PURE__ */ jsx("span", { className: "text-zinc-400", children: endpoint })
      ] }),
      hasBody && /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx("div", { className: "mb-2 text-xs text-zinc-400", children: "Request Body" }),
        /* @__PURE__ */ jsxs("div", { className: "text-xs leading-relaxed text-zinc-100", children: [
          /* @__PURE__ */ jsx("div", { children: "{" }),
          entries.map(([key, value], idx) => /* @__PURE__ */ jsxs(React.Fragment, { children: [
            /* @__PURE__ */ jsx(
              JsonValue,
              {
                keyName: key,
                value,
                path: [key],
                editable: editable && !!onBodyChange,
                onValueChange: handleValueChange,
                indent: 1
              }
            ),
            idx < entries.length - 1 && /* @__PURE__ */ jsx("span", { className: "pl-4 text-zinc-500", children: "," })
          ] }, key)),
          /* @__PURE__ */ jsx("div", { children: "}" })
        ] })
      ] })
    ] }),
    editable && onBodyChange && /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-3 text-xs", children: "Edit values above or use the Form tab for a guided experience." })
  ] });
}
function Footer({ children, className }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className
      ),
      children
    }
  );
}
ApiForm.Toggle = Toggle;
ApiForm.FormView = FormView;
ApiForm.CodeView = CodeView;
ApiForm.Footer = Footer;
export {
  ApiForm as A
};
