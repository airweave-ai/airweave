import { jsxs, jsx } from "react/jsx-runtime";
import * as React from "react";
import { a as cn } from "./router-BGxBdlkD.mjs";
function EmptyState({
  icon,
  title,
  description,
  children,
  className
}) {
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className
      ),
      children: [
        /* @__PURE__ */ jsx("div", { className: "flex size-16 items-center justify-center", children: React.isValidElement(icon) ? React.cloneElement(
          icon,
          {
            className: cn(
              "size-8 text-muted-foreground",
              icon.props?.className
            )
          }
        ) : icon }),
        /* @__PURE__ */ jsx("h2", { className: "text-muted-foreground mb-2 font-mono font-medium uppercase opacity-70", children: title }),
        /* @__PURE__ */ jsx("p", { className: "text-muted-foreground max-w-sm text-sm", children: description }),
        children && /* @__PURE__ */ jsx("div", { className: "mt-4", children })
      ]
    }
  );
}
export {
  EmptyState as E
};
