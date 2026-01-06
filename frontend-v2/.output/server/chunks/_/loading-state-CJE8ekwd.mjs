import { jsx, jsxs } from "react/jsx-runtime";
import { a as cn, L as LoaderCircle } from "./router-BGxBdlkD.mjs";
function LoadingState({
  message,
  className,
  size = "md"
}) {
  const sizeClasses = {
    sm: "size-4",
    md: "size-6",
    lg: "size-8"
  };
  const paddingClasses = {
    sm: "py-8",
    md: "py-20",
    lg: "py-32"
  };
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "flex items-center justify-center",
        paddingClasses[size],
        className
      ),
      children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center gap-3", children: [
        /* @__PURE__ */ jsx(
          LoaderCircle,
          {
            className: cn(
              "text-muted-foreground animate-spin",
              sizeClasses[size]
            )
          }
        ),
        message && /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: message })
      ] })
    }
  );
}
export {
  LoadingState as L
};
