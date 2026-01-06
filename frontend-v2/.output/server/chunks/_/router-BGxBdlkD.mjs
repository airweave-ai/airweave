import { createRouter, createRootRoute, createFileRoute, lazyRouteComponent, HeadContent, Scripts, useParams, Outlet, redirect, useNavigate, useLocation, Link } from "@tanstack/react-router";
import { jsxs, jsx, Fragment } from "react/jsx-runtime";
import { QueryClient, useQueryClient, useIsRestoring, useQuery } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import * as React from "react";
import React__default, { forwardRef, createElement, useState, useReducer, useRef, useCallback, useEffect, useMemo, createContext, useContext, useSyncExternalStore } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import * as SheetPrimitive from "@radix-ui/react-dialog";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import * as AvatarPrimitive from "@radix-ui/react-avatar";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { Command as Command$1 } from "cmdk";
import { Toaster as Toaster$1 } from "sonner";
import { del, get, set } from "idb-keyval";
const toKebabCase = (string) => string.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
const toCamelCase = (string) => string.replace(
  /^([A-Z])|[\s-_]+(\w)/g,
  (match, p1, p2) => p2 ? p2.toUpperCase() : p1.toLowerCase()
);
const toPascalCase = (string) => {
  const camelCase = toCamelCase(string);
  return camelCase.charAt(0).toUpperCase() + camelCase.slice(1);
};
const mergeClasses = (...classes) => classes.filter((className, index, array) => {
  return Boolean(className) && className.trim() !== "" && array.indexOf(className) === index;
}).join(" ").trim();
const hasA11yProp = (props) => {
  for (const prop in props) {
    if (prop.startsWith("aria-") || prop === "role" || prop === "title") {
      return true;
    }
  }
};
var defaultAttributes = {
  xmlns: "http://www.w3.org/2000/svg",
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round"
};
const Icon = forwardRef(
  ({
    color = "currentColor",
    size = 24,
    strokeWidth = 2,
    absoluteStrokeWidth,
    className = "",
    children,
    iconNode,
    ...rest
  }, ref) => createElement(
    "svg",
    {
      ref,
      ...defaultAttributes,
      width: size,
      height: size,
      stroke: color,
      strokeWidth: absoluteStrokeWidth ? Number(strokeWidth) * 24 / Number(size) : strokeWidth,
      className: mergeClasses("lucide", className),
      ...!children && !hasA11yProp(rest) && { "aria-hidden": "true" },
      ...rest
    },
    [
      ...iconNode.map(([tag, attrs]) => createElement(tag, attrs)),
      ...Array.isArray(children) ? children : [children]
    ]
  )
);
const createLucideIcon = (iconName, iconNode) => {
  const Component = forwardRef(
    ({ className, ...props }, ref) => createElement(Icon, {
      ref,
      iconNode,
      className: mergeClasses(
        `lucide-${toKebabCase(toPascalCase(iconName))}`,
        `lucide-${iconName}`,
        className
      ),
      ...props
    })
  );
  Component.displayName = toPascalCase(iconName);
  return Component;
};
const __iconNode$o = [
  ["path", { d: "M12 7v14", key: "1akyts" }],
  [
    "path",
    {
      d: "M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z",
      key: "ruj8y"
    }
  ]
];
const BookOpen = createLucideIcon("book-open", __iconNode$o);
const __iconNode$n = [
  ["path", { d: "M10 12h4", key: "a56b0p" }],
  ["path", { d: "M10 8h4", key: "1sr2af" }],
  ["path", { d: "M14 21v-3a2 2 0 0 0-4 0v3", key: "1rgiei" }],
  [
    "path",
    {
      d: "M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2",
      key: "secmi2"
    }
  ],
  ["path", { d: "M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16", key: "16ra0t" }]
];
const Building2 = createLucideIcon("building-2", __iconNode$n);
const __iconNode$m = [["path", { d: "M20 6 9 17l-5-5", key: "1gmf2c" }]];
const Check = createLucideIcon("check", __iconNode$m);
const __iconNode$l = [["path", { d: "m9 18 6-6-6-6", key: "mthhwq" }]];
const ChevronRight = createLucideIcon("chevron-right", __iconNode$l);
const __iconNode$k = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "m9 12 2 2 4-4", key: "dzmm74" }]
];
const CircleCheck = createLucideIcon("circle-check", __iconNode$k);
const __iconNode$j = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3", key: "1u773s" }],
  ["path", { d: "M12 17h.01", key: "p32p05" }]
];
const CircleQuestionMark = createLucideIcon("circle-question-mark", __iconNode$j);
const __iconNode$i = [
  ["path", { d: "m18 16 4-4-4-4", key: "1inbqp" }],
  ["path", { d: "m6 8-4 4 4 4", key: "15zrgr" }],
  ["path", { d: "m14.5 4-5 16", key: "e7oirm" }]
];
const CodeXml = createLucideIcon("code-xml", __iconNode$i);
const __iconNode$h = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M12 16v-4", key: "1dtifu" }],
  ["path", { d: "M12 8h.01", key: "e9boi3" }]
];
const Info = createLucideIcon("info", __iconNode$h);
const __iconNode$g = [
  ["path", { d: "m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4", key: "g0fldk" }],
  ["path", { d: "m21 2-9.6 9.6", key: "1j0ho8" }],
  ["circle", { cx: "7.5", cy: "15.5", r: "5.5", key: "yqb3hr" }]
];
const Key = createLucideIcon("key", __iconNode$g);
const __iconNode$f = [
  ["rect", { width: "7", height: "7", x: "3", y: "3", rx: "1", key: "1g98yp" }],
  ["rect", { width: "7", height: "7", x: "14", y: "3", rx: "1", key: "6d4xhi" }],
  ["rect", { width: "7", height: "7", x: "14", y: "14", rx: "1", key: "nxv5o0" }],
  ["rect", { width: "7", height: "7", x: "3", y: "14", rx: "1", key: "1bb6yr" }]
];
const LayoutGrid = createLucideIcon("layout-grid", __iconNode$f);
const __iconNode$e = [["path", { d: "M21 12a9 9 0 1 1-6.219-8.56", key: "13zald" }]];
const LoaderCircle = createLucideIcon("loader-circle", __iconNode$e);
const __iconNode$d = [
  ["path", { d: "m16 17 5-5-5-5", key: "1bji2h" }],
  ["path", { d: "M21 12H9", key: "dn1m92" }],
  ["path", { d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", key: "1uf3rs" }]
];
const LogOut = createLucideIcon("log-out", __iconNode$d);
const __iconNode$c = [
  ["rect", { width: "20", height: "14", x: "2", y: "3", rx: "2", key: "48i651" }],
  ["line", { x1: "8", x2: "16", y1: "21", y2: "21", key: "1svkeh" }],
  ["line", { x1: "12", x2: "12", y1: "17", y2: "21", key: "vw1qmm" }]
];
const Monitor = createLucideIcon("monitor", __iconNode$c);
const __iconNode$b = [
  [
    "path",
    {
      d: "M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401",
      key: "kfwtm"
    }
  ]
];
const Moon = createLucideIcon("moon", __iconNode$b);
const __iconNode$a = [
  ["path", { d: "m15 9-6 6", key: "1uzhvr" }],
  [
    "path",
    {
      d: "M2.586 16.726A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2h6.624a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586z",
      key: "2d38gg"
    }
  ],
  ["path", { d: "m9 9 6 6", key: "z0biqf" }]
];
const OctagonX = createLucideIcon("octagon-x", __iconNode$a);
const __iconNode$9 = [
  [
    "path",
    {
      d: "M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z",
      key: "e79jfc"
    }
  ],
  ["circle", { cx: "13.5", cy: "6.5", r: ".5", fill: "currentColor", key: "1okk4w" }],
  ["circle", { cx: "17.5", cy: "10.5", r: ".5", fill: "currentColor", key: "f64h9f" }],
  ["circle", { cx: "6.5", cy: "12.5", r: ".5", fill: "currentColor", key: "qy21gx" }],
  ["circle", { cx: "8.5", cy: "7.5", r: ".5", fill: "currentColor", key: "fotxhn" }]
];
const Palette = createLucideIcon("palette", __iconNode$9);
const __iconNode$8 = [
  ["rect", { width: "18", height: "18", x: "3", y: "3", rx: "2", key: "afitv7" }],
  ["path", { d: "M9 3v18", key: "fh3hqa" }]
];
const PanelLeft = createLucideIcon("panel-left", __iconNode$8);
const __iconNode$7 = [
  ["path", { d: "M5 12h14", key: "1ays0h" }],
  ["path", { d: "M12 5v14", key: "s699le" }]
];
const Plus = createLucideIcon("plus", __iconNode$7);
const __iconNode$6 = [
  ["path", { d: "m21 21-4.34-4.34", key: "14j7rj" }],
  ["circle", { cx: "11", cy: "11", r: "8", key: "4ej97u" }]
];
const Search = createLucideIcon("search", __iconNode$6);
const __iconNode$5 = [
  [
    "path",
    {
      d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      key: "oel41y"
    }
  ],
  ["path", { d: "m9 12 2 2 4-4", key: "dzmm74" }]
];
const ShieldCheck = createLucideIcon("shield-check", __iconNode$5);
const __iconNode$4 = [
  ["circle", { cx: "12", cy: "12", r: "4", key: "4exip2" }],
  ["path", { d: "M12 2v2", key: "tus03m" }],
  ["path", { d: "M12 20v2", key: "1lh1kg" }],
  ["path", { d: "m4.93 4.93 1.41 1.41", key: "149t6j" }],
  ["path", { d: "m17.66 17.66 1.41 1.41", key: "ptbguv" }],
  ["path", { d: "M2 12h2", key: "1t8f8n" }],
  ["path", { d: "M20 12h2", key: "1q8mjw" }],
  ["path", { d: "m6.34 17.66-1.41 1.41", key: "1m8zz5" }],
  ["path", { d: "m19.07 4.93-1.41 1.41", key: "1shlcs" }]
];
const Sun = createLucideIcon("sun", __iconNode$4);
const __iconNode$3 = [
  ["path", { d: "M12 19h8", key: "baeox8" }],
  ["path", { d: "m4 17 6-6-6-6", key: "1yngyt" }]
];
const Terminal = createLucideIcon("terminal", __iconNode$3);
const __iconNode$2 = [
  [
    "path",
    {
      d: "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",
      key: "wmoenq"
    }
  ],
  ["path", { d: "M12 9v4", key: "juzpu7" }],
  ["path", { d: "M12 17h.01", key: "p32p05" }]
];
const TriangleAlert = createLucideIcon("triangle-alert", __iconNode$2);
const __iconNode$1 = [
  [
    "path",
    {
      d: "M18 16.98h-5.99c-1.1 0-1.95.94-2.48 1.9A4 4 0 0 1 2 17c.01-.7.2-1.4.57-2",
      key: "q3hayz"
    }
  ],
  ["path", { d: "m6 17 3.13-5.78c.53-.97.1-2.18-.5-3.1a4 4 0 1 1 6.89-4.06", key: "1go1hn" }],
  ["path", { d: "m12 6 3.13 5.73C15.66 12.7 16.9 13 18 13a4 4 0 0 1 0 8", key: "qlwsc0" }]
];
const Webhook = createLucideIcon("webhook", __iconNode$1);
const __iconNode = [
  ["path", { d: "M18 6 6 18", key: "1bl5f8" }],
  ["path", { d: "m6 6 12 12", key: "d8bk6v" }]
];
const X$1 = createLucideIcon("x", __iconNode);
var extendStatics = function(d2, b2) {
  extendStatics = Object.setPrototypeOf || { __proto__: [] } instanceof Array && function(d3, b3) {
    d3.__proto__ = b3;
  } || function(d3, b3) {
    for (var p2 in b3) if (Object.prototype.hasOwnProperty.call(b3, p2)) d3[p2] = b3[p2];
  };
  return extendStatics(d2, b2);
};
function __extends(d2, b2) {
  if (typeof b2 !== "function" && b2 !== null)
    throw new TypeError("Class extends value " + String(b2) + " is not a constructor or null");
  extendStatics(d2, b2);
  function __() {
    this.constructor = d2;
  }
  d2.prototype = b2 === null ? Object.create(b2) : (__.prototype = b2.prototype, new __());
}
var __assign = function() {
  __assign = Object.assign || function __assign2(t2) {
    for (var s2, i2 = 1, n2 = arguments.length; i2 < n2; i2++) {
      s2 = arguments[i2];
      for (var p2 in s2) if (Object.prototype.hasOwnProperty.call(s2, p2)) t2[p2] = s2[p2];
    }
    return t2;
  };
  return __assign.apply(this, arguments);
};
function __rest(s2, e2) {
  var t2 = {};
  for (var p2 in s2) if (Object.prototype.hasOwnProperty.call(s2, p2) && e2.indexOf(p2) < 0)
    t2[p2] = s2[p2];
  if (s2 != null && typeof Object.getOwnPropertySymbols === "function")
    for (var i2 = 0, p2 = Object.getOwnPropertySymbols(s2); i2 < p2.length; i2++) {
      if (e2.indexOf(p2[i2]) < 0 && Object.prototype.propertyIsEnumerable.call(s2, p2[i2]))
        t2[p2[i2]] = s2[p2[i2]];
    }
  return t2;
}
function __awaiter(thisArg, _arguments, P2, generator) {
  function adopt(value) {
    return value instanceof P2 ? value : new P2(function(resolve) {
      resolve(value);
    });
  }
  return new (P2 || (P2 = Promise))(function(resolve, reject) {
    function fulfilled(value) {
      try {
        step(generator.next(value));
      } catch (e2) {
        reject(e2);
      }
    }
    function rejected(value) {
      try {
        step(generator["throw"](value));
      } catch (e2) {
        reject(e2);
      }
    }
    function step(result) {
      result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
    }
    step((generator = generator.apply(thisArg, _arguments || [])).next());
  });
}
function __generator(thisArg, body) {
  var _2 = { label: 0, sent: function() {
    if (t2[0] & 1) throw t2[1];
    return t2[1];
  }, trys: [], ops: [] }, f2, y2, t2, g2 = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
  return g2.next = verb(0), g2["throw"] = verb(1), g2["return"] = verb(2), typeof Symbol === "function" && (g2[Symbol.iterator] = function() {
    return this;
  }), g2;
  function verb(n2) {
    return function(v2) {
      return step([n2, v2]);
    };
  }
  function step(op) {
    if (f2) throw new TypeError("Generator is already executing.");
    while (g2 && (g2 = 0, op[0] && (_2 = 0)), _2) try {
      if (f2 = 1, y2 && (t2 = op[0] & 2 ? y2["return"] : op[0] ? y2["throw"] || ((t2 = y2["return"]) && t2.call(y2), 0) : y2.next) && !(t2 = t2.call(y2, op[1])).done) return t2;
      if (y2 = 0, t2) op = [op[0] & 2, t2.value];
      switch (op[0]) {
        case 0:
        case 1:
          t2 = op;
          break;
        case 4:
          _2.label++;
          return { value: op[1], done: false };
        case 5:
          _2.label++;
          y2 = op[1];
          op = [0];
          continue;
        case 7:
          op = _2.ops.pop();
          _2.trys.pop();
          continue;
        default:
          if (!(t2 = _2.trys, t2 = t2.length > 0 && t2[t2.length - 1]) && (op[0] === 6 || op[0] === 2)) {
            _2 = 0;
            continue;
          }
          if (op[0] === 3 && (!t2 || op[1] > t2[0] && op[1] < t2[3])) {
            _2.label = op[1];
            break;
          }
          if (op[0] === 6 && _2.label < t2[1]) {
            _2.label = t2[1];
            t2 = op;
            break;
          }
          if (t2 && _2.label < t2[2]) {
            _2.label = t2[2];
            _2.ops.push(op);
            break;
          }
          if (t2[2]) _2.ops.pop();
          _2.trys.pop();
          continue;
      }
      op = body.call(thisArg, _2);
    } catch (e2) {
      op = [6, e2];
      y2 = 0;
    } finally {
      f2 = t2 = 0;
    }
    if (op[0] & 5) throw op[1];
    return { value: op[0] ? op[1] : void 0, done: true };
  }
}
function __spreadArray(to, from, pack) {
  for (var i2 = 0, l2 = from.length, ar; i2 < l2; i2++) {
    if (ar || !(i2 in from)) {
      if (!ar) ar = Array.prototype.slice.call(from, 0, i2);
      ar[i2] = from[i2];
    }
  }
  return to.concat(ar || Array.prototype.slice.call(from));
}
typeof SuppressedError === "function" ? SuppressedError : function(error, suppressed, message) {
  var e2 = new Error(message);
  return e2.name = "SuppressedError", e2.error = error, e2.suppressed = suppressed, e2;
};
function e(e2, t2) {
  var o2 = {};
  for (var n2 in e2) Object.prototype.hasOwnProperty.call(e2, n2) && t2.indexOf(n2) < 0 && (o2[n2] = e2[n2]);
  if (null != e2 && "function" == typeof Object.getOwnPropertySymbols) {
    var i2 = 0;
    for (n2 = Object.getOwnPropertySymbols(e2); i2 < n2.length; i2++) t2.indexOf(n2[i2]) < 0 && Object.prototype.propertyIsEnumerable.call(e2, n2[i2]) && (o2[n2[i2]] = e2[n2[i2]]);
  }
  return o2;
}
"function" == typeof SuppressedError && SuppressedError;
var t = "undefined" != typeof globalThis ? globalThis : "undefined" != typeof window ? window : "undefined" != typeof global ? global : "undefined" != typeof self ? self : {};
function o(e2) {
  return e2 && e2.__esModule && Object.prototype.hasOwnProperty.call(e2, "default") ? e2.default : e2;
}
function n(e2, t2) {
  return e2(t2 = { exports: {} }, t2.exports), t2.exports;
}
var i = n((function(e2, t2) {
  Object.defineProperty(t2, "__esModule", { value: true });
  var o2 = (function() {
    function e3() {
      var e4 = this;
      this.locked = /* @__PURE__ */ new Map(), this.addToLocked = function(t3, o3) {
        var n2 = e4.locked.get(t3);
        void 0 === n2 ? void 0 === o3 ? e4.locked.set(t3, []) : e4.locked.set(t3, [o3]) : void 0 !== o3 && (n2.unshift(o3), e4.locked.set(t3, n2));
      }, this.isLocked = function(t3) {
        return e4.locked.has(t3);
      }, this.lock = function(t3) {
        return new Promise((function(o3, n2) {
          e4.isLocked(t3) ? e4.addToLocked(t3, o3) : (e4.addToLocked(t3), o3());
        }));
      }, this.unlock = function(t3) {
        var o3 = e4.locked.get(t3);
        if (void 0 !== o3 && 0 !== o3.length) {
          var n2 = o3.pop();
          e4.locked.set(t3, o3), void 0 !== n2 && setTimeout(n2, 0);
        } else e4.locked.delete(t3);
      };
    }
    return e3.getInstance = function() {
      return void 0 === e3.instance && (e3.instance = new e3()), e3.instance;
    }, e3;
  })();
  t2.default = function() {
    return o2.getInstance();
  };
}));
o(i);
var r = o(n((function(e2, o2) {
  var n2 = t && t.__awaiter || function(e3, t2, o3, n3) {
    return new (o3 || (o3 = Promise))((function(i2, r3) {
      function s3(e4) {
        try {
          c3(n3.next(e4));
        } catch (e5) {
          r3(e5);
        }
      }
      function a3(e4) {
        try {
          c3(n3.throw(e4));
        } catch (e5) {
          r3(e5);
        }
      }
      function c3(e4) {
        e4.done ? i2(e4.value) : new o3((function(t3) {
          t3(e4.value);
        })).then(s3, a3);
      }
      c3((n3 = n3.apply(e3, t2 || [])).next());
    }));
  }, r2 = t && t.__generator || function(e3, t2) {
    var o3, n3, i2, r3, s3 = { label: 0, sent: function() {
      if (1 & i2[0]) throw i2[1];
      return i2[1];
    }, trys: [], ops: [] };
    return r3 = { next: a3(0), throw: a3(1), return: a3(2) }, "function" == typeof Symbol && (r3[Symbol.iterator] = function() {
      return this;
    }), r3;
    function a3(r4) {
      return function(a4) {
        return (function(r5) {
          if (o3) throw new TypeError("Generator is already executing.");
          for (; s3; ) try {
            if (o3 = 1, n3 && (i2 = 2 & r5[0] ? n3.return : r5[0] ? n3.throw || ((i2 = n3.return) && i2.call(n3), 0) : n3.next) && !(i2 = i2.call(n3, r5[1])).done) return i2;
            switch (n3 = 0, i2 && (r5 = [2 & r5[0], i2.value]), r5[0]) {
              case 0:
              case 1:
                i2 = r5;
                break;
              case 4:
                return s3.label++, { value: r5[1], done: false };
              case 5:
                s3.label++, n3 = r5[1], r5 = [0];
                continue;
              case 7:
                r5 = s3.ops.pop(), s3.trys.pop();
                continue;
              default:
                if (!(i2 = s3.trys, (i2 = i2.length > 0 && i2[i2.length - 1]) || 6 !== r5[0] && 2 !== r5[0])) {
                  s3 = 0;
                  continue;
                }
                if (3 === r5[0] && (!i2 || r5[1] > i2[0] && r5[1] < i2[3])) {
                  s3.label = r5[1];
                  break;
                }
                if (6 === r5[0] && s3.label < i2[1]) {
                  s3.label = i2[1], i2 = r5;
                  break;
                }
                if (i2 && s3.label < i2[2]) {
                  s3.label = i2[2], s3.ops.push(r5);
                  break;
                }
                i2[2] && s3.ops.pop(), s3.trys.pop();
                continue;
            }
            r5 = t2.call(e3, s3);
          } catch (e4) {
            r5 = [6, e4], n3 = 0;
          } finally {
            o3 = i2 = 0;
          }
          if (5 & r5[0]) throw r5[1];
          return { value: r5[0] ? r5[1] : void 0, done: true };
        })([r4, a4]);
      };
    }
  }, s2 = t;
  Object.defineProperty(o2, "__esModule", { value: true });
  var a2 = "browser-tabs-lock-key", c2 = { key: function(e3) {
    return n2(s2, void 0, void 0, (function() {
      return r2(this, (function(e4) {
        throw new Error("Unsupported");
      }));
    }));
  }, getItem: function(e3) {
    return n2(s2, void 0, void 0, (function() {
      return r2(this, (function(e4) {
        throw new Error("Unsupported");
      }));
    }));
  }, clear: function() {
    return n2(s2, void 0, void 0, (function() {
      return r2(this, (function(e3) {
        return [2, window.localStorage.clear()];
      }));
    }));
  }, removeItem: function(e3) {
    return n2(s2, void 0, void 0, (function() {
      return r2(this, (function(e4) {
        throw new Error("Unsupported");
      }));
    }));
  }, setItem: function(e3, t2) {
    return n2(s2, void 0, void 0, (function() {
      return r2(this, (function(e4) {
        throw new Error("Unsupported");
      }));
    }));
  }, keySync: function(e3) {
    return window.localStorage.key(e3);
  }, getItemSync: function(e3) {
    return window.localStorage.getItem(e3);
  }, clearSync: function() {
    return window.localStorage.clear();
  }, removeItemSync: function(e3) {
    return window.localStorage.removeItem(e3);
  }, setItemSync: function(e3, t2) {
    return window.localStorage.setItem(e3, t2);
  } };
  function u2(e3) {
    return new Promise((function(t2) {
      return setTimeout(t2, e3);
    }));
  }
  function d2(e3) {
    for (var t2 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXTZabcdefghiklmnopqrstuvwxyz", o3 = "", n3 = 0; n3 < e3; n3++) {
      o3 += t2[Math.floor(Math.random() * t2.length)];
    }
    return o3;
  }
  var h2 = (function() {
    function e3(t2) {
      this.acquiredIatSet = /* @__PURE__ */ new Set(), this.storageHandler = void 0, this.id = Date.now().toString() + d2(15), this.acquireLock = this.acquireLock.bind(this), this.releaseLock = this.releaseLock.bind(this), this.releaseLock__private__ = this.releaseLock__private__.bind(this), this.waitForSomethingToChange = this.waitForSomethingToChange.bind(this), this.refreshLockWhileAcquired = this.refreshLockWhileAcquired.bind(this), this.storageHandler = t2, void 0 === e3.waiters && (e3.waiters = []);
    }
    return e3.prototype.acquireLock = function(t2, o3) {
      return void 0 === o3 && (o3 = 5e3), n2(this, void 0, void 0, (function() {
        var n3, i2, s3, h3, l2, p2, m2;
        return r2(this, (function(r3) {
          switch (r3.label) {
            case 0:
              n3 = Date.now() + d2(4), i2 = Date.now() + o3, s3 = a2 + "-" + t2, h3 = void 0 === this.storageHandler ? c2 : this.storageHandler, r3.label = 1;
            case 1:
              return Date.now() < i2 ? [4, u2(30)] : [3, 8];
            case 2:
              return r3.sent(), null !== h3.getItemSync(s3) ? [3, 5] : (l2 = this.id + "-" + t2 + "-" + n3, [4, u2(Math.floor(25 * Math.random()))]);
            case 3:
              return r3.sent(), h3.setItemSync(s3, JSON.stringify({ id: this.id, iat: n3, timeoutKey: l2, timeAcquired: Date.now(), timeRefreshed: Date.now() })), [4, u2(30)];
            case 4:
              return r3.sent(), null !== (p2 = h3.getItemSync(s3)) && (m2 = JSON.parse(p2)).id === this.id && m2.iat === n3 ? (this.acquiredIatSet.add(n3), this.refreshLockWhileAcquired(s3, n3), [2, true]) : [3, 7];
            case 5:
              return e3.lockCorrector(void 0 === this.storageHandler ? c2 : this.storageHandler), [4, this.waitForSomethingToChange(i2)];
            case 6:
              r3.sent(), r3.label = 7;
            case 7:
              return n3 = Date.now() + d2(4), [3, 1];
            case 8:
              return [2, false];
          }
        }));
      }));
    }, e3.prototype.refreshLockWhileAcquired = function(e4, t2) {
      return n2(this, void 0, void 0, (function() {
        var o3 = this;
        return r2(this, (function(s3) {
          return setTimeout((function() {
            return n2(o3, void 0, void 0, (function() {
              var o4, n3, s4;
              return r2(this, (function(r3) {
                switch (r3.label) {
                  case 0:
                    return [4, i.default().lock(t2)];
                  case 1:
                    return r3.sent(), this.acquiredIatSet.has(t2) ? (o4 = void 0 === this.storageHandler ? c2 : this.storageHandler, null === (n3 = o4.getItemSync(e4)) ? (i.default().unlock(t2), [2]) : ((s4 = JSON.parse(n3)).timeRefreshed = Date.now(), o4.setItemSync(e4, JSON.stringify(s4)), i.default().unlock(t2), this.refreshLockWhileAcquired(e4, t2), [2])) : (i.default().unlock(t2), [2]);
                }
              }));
            }));
          }), 1e3), [2];
        }));
      }));
    }, e3.prototype.waitForSomethingToChange = function(t2) {
      return n2(this, void 0, void 0, (function() {
        return r2(this, (function(o3) {
          switch (o3.label) {
            case 0:
              return [4, new Promise((function(o4) {
                var n3 = false, i2 = Date.now(), r3 = false;
                function s3() {
                  if (r3 || (window.removeEventListener("storage", s3), e3.removeFromWaiting(s3), clearTimeout(a3), r3 = true), !n3) {
                    n3 = true;
                    var t3 = 50 - (Date.now() - i2);
                    t3 > 0 ? setTimeout(o4, t3) : o4(null);
                  }
                }
                window.addEventListener("storage", s3), e3.addToWaiting(s3);
                var a3 = setTimeout(s3, Math.max(0, t2 - Date.now()));
              }))];
            case 1:
              return o3.sent(), [2];
          }
        }));
      }));
    }, e3.addToWaiting = function(t2) {
      this.removeFromWaiting(t2), void 0 !== e3.waiters && e3.waiters.push(t2);
    }, e3.removeFromWaiting = function(t2) {
      void 0 !== e3.waiters && (e3.waiters = e3.waiters.filter((function(e4) {
        return e4 !== t2;
      })));
    }, e3.notifyWaiters = function() {
      void 0 !== e3.waiters && e3.waiters.slice().forEach((function(e4) {
        return e4();
      }));
    }, e3.prototype.releaseLock = function(e4) {
      return n2(this, void 0, void 0, (function() {
        return r2(this, (function(t2) {
          switch (t2.label) {
            case 0:
              return [4, this.releaseLock__private__(e4)];
            case 1:
              return [2, t2.sent()];
          }
        }));
      }));
    }, e3.prototype.releaseLock__private__ = function(t2) {
      return n2(this, void 0, void 0, (function() {
        var o3, n3, s3, u3;
        return r2(this, (function(r3) {
          switch (r3.label) {
            case 0:
              return o3 = void 0 === this.storageHandler ? c2 : this.storageHandler, n3 = a2 + "-" + t2, null === (s3 = o3.getItemSync(n3)) ? [2] : (u3 = JSON.parse(s3)).id !== this.id ? [3, 2] : [4, i.default().lock(u3.iat)];
            case 1:
              r3.sent(), this.acquiredIatSet.delete(u3.iat), o3.removeItemSync(n3), i.default().unlock(u3.iat), e3.notifyWaiters(), r3.label = 2;
            case 2:
              return [2];
          }
        }));
      }));
    }, e3.lockCorrector = function(t2) {
      for (var o3 = Date.now() - 5e3, n3 = t2, i2 = [], r3 = 0; ; ) {
        var s3 = n3.keySync(r3);
        if (null === s3) break;
        i2.push(s3), r3++;
      }
      for (var c3 = false, u3 = 0; u3 < i2.length; u3++) {
        var d3 = i2[u3];
        if (d3.includes(a2)) {
          var h3 = n3.getItemSync(d3);
          if (null !== h3) {
            var l2 = JSON.parse(h3);
            (void 0 === l2.timeRefreshed && l2.timeAcquired < o3 || void 0 !== l2.timeRefreshed && l2.timeRefreshed < o3) && (n3.removeItemSync(d3), c3 = true);
          }
        }
      }
      c3 && e3.notifyWaiters();
    }, e3.waiters = void 0, e3;
  })();
  o2.default = h2;
})));
const s = { timeoutInSeconds: 60 }, a = { name: "auth0-spa-js", version: "2.11.0" }, c = () => Date.now();
class u extends Error {
  constructor(e2, t2) {
    super(t2), this.error = e2, this.error_description = t2, Object.setPrototypeOf(this, u.prototype);
  }
  static fromPayload({ error: e2, error_description: t2 }) {
    return new u(e2, t2);
  }
}
class d extends u {
  constructor(e2, t2, o2, n2 = null) {
    super(e2, t2), this.state = o2, this.appState = n2, Object.setPrototypeOf(this, d.prototype);
  }
}
class h extends u {
  constructor(e2, t2, o2, n2, i2 = null) {
    super(e2, t2), this.connection = o2, this.state = n2, this.appState = i2, Object.setPrototypeOf(this, h.prototype);
  }
}
class l extends u {
  constructor() {
    super("timeout", "Timeout"), Object.setPrototypeOf(this, l.prototype);
  }
}
class p extends l {
  constructor(e2) {
    super(), this.popup = e2, Object.setPrototypeOf(this, p.prototype);
  }
}
class m extends u {
  constructor(e2) {
    super("cancelled", "Popup closed"), this.popup = e2, Object.setPrototypeOf(this, m.prototype);
  }
}
class f extends u {
  constructor() {
    super("popup_open", "Unable to open a popup for loginWithPopup - window.open returned `null`"), Object.setPrototypeOf(this, f.prototype);
  }
}
class g extends u {
  constructor(e2, t2, o2) {
    super(e2, t2), this.mfa_token = o2, Object.setPrototypeOf(this, g.prototype);
  }
}
class y extends u {
  constructor(e2, t2) {
    super("missing_refresh_token", `Missing Refresh Token (audience: '${k(e2, ["default"])}', scope: '${k(t2)}')`), this.audience = e2, this.scope = t2, Object.setPrototypeOf(this, y.prototype);
  }
}
class w extends u {
  constructor(e2, t2) {
    super("missing_scopes", `Missing requested scopes after refresh (audience: '${k(e2, ["default"])}', missing scope: '${k(t2)}')`), this.audience = e2, this.scope = t2, Object.setPrototypeOf(this, w.prototype);
  }
}
class b extends u {
  constructor(e2) {
    super("use_dpop_nonce", "Server rejected DPoP proof: wrong nonce"), this.newDpopNonce = e2, Object.setPrototypeOf(this, b.prototype);
  }
}
function k(e2, t2 = []) {
  return e2 && !t2.includes(e2) ? e2 : "";
}
const v = () => window.crypto, _ = () => {
  const e2 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_~.";
  let t2 = "";
  return Array.from(v().getRandomValues(new Uint8Array(43))).forEach(((o2) => t2 += e2[o2 % e2.length])), t2;
}, S = (e2) => btoa(e2), I = [{ key: "name", type: ["string"] }, { key: "version", type: ["string", "number"] }, { key: "env", type: ["object"] }], P = (e2) => Object.keys(e2).reduce(((t2, o2) => {
  const n2 = I.find(((e3) => e3.key === o2));
  return n2 && n2.type.includes(typeof e2[o2]) && (t2[o2] = e2[o2]), t2;
}), {}), T = (t2) => {
  var { clientId: o2 } = t2, n2 = e(t2, ["clientId"]);
  return new URLSearchParams(((e2) => Object.keys(e2).filter(((t3) => void 0 !== e2[t3])).reduce(((t3, o3) => Object.assign(Object.assign({}, t3), { [o3]: e2[o3] })), {}))(Object.assign({ client_id: o2 }, n2))).toString();
}, O = async (e2) => {
  const t2 = v().subtle.digest({ name: "SHA-256" }, new TextEncoder().encode(e2));
  return await t2;
}, j = (e2) => ((e3) => decodeURIComponent(atob(e3).split("").map(((e4) => "%" + ("00" + e4.charCodeAt(0).toString(16)).slice(-2))).join("")))(e2.replace(/_/g, "/").replace(/-/g, "+")), C = (e2) => {
  const t2 = new Uint8Array(e2);
  return ((e3) => {
    const t3 = { "+": "-", "/": "_", "=": "" };
    return e3.replace(/[+/=]/g, ((e4) => t3[e4]));
  })(window.btoa(String.fromCharCode(...Array.from(t2))));
}, K = new TextEncoder(), x = new TextDecoder();
function z(e2) {
  return "string" == typeof e2 ? K.encode(e2) : x.decode(e2);
}
function E(e2) {
  if ("number" != typeof e2.modulusLength || e2.modulusLength < 2048) throw new U(`${e2.name} modulusLength must be at least 2048 bits`);
}
async function N(e2, t2, o2) {
  if (false === o2.usages.includes("sign")) throw new TypeError('private CryptoKey instances used for signing assertions must include "sign" in their "usages"');
  const n2 = `${D(z(JSON.stringify(e2)))}.${D(z(JSON.stringify(t2)))}`;
  return `${n2}.${D(await crypto.subtle.sign((function(e3) {
    switch (e3.algorithm.name) {
      case "ECDSA":
        return { name: e3.algorithm.name, hash: "SHA-256" };
      case "RSA-PSS":
        return E(e3.algorithm), { name: e3.algorithm.name, saltLength: 32 };
      case "RSASSA-PKCS1-v1_5":
        return E(e3.algorithm), { name: e3.algorithm.name };
      case "Ed25519":
        return { name: e3.algorithm.name };
    }
    throw new A();
  })(o2), o2, z(n2)))}`;
}
let R;
if (Uint8Array.prototype.toBase64) R = (e2) => (e2 instanceof ArrayBuffer && (e2 = new Uint8Array(e2)), e2.toBase64({ alphabet: "base64url", omitPadding: true }));
else {
  const e2 = 32768;
  R = (t2) => {
    t2 instanceof ArrayBuffer && (t2 = new Uint8Array(t2));
    const o2 = [];
    for (let n2 = 0; n2 < t2.byteLength; n2 += e2) o2.push(String.fromCharCode.apply(null, t2.subarray(n2, n2 + e2)));
    return btoa(o2.join("")).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  };
}
function D(e2) {
  return R(e2);
}
class A extends Error {
  constructor(e2) {
    var t2;
    super(null != e2 ? e2 : "operation not supported"), this.name = this.constructor.name, null === (t2 = Error.captureStackTrace) || void 0 === t2 || t2.call(Error, this, this.constructor);
  }
}
class U extends Error {
  constructor(e2) {
    var t2;
    super(e2), this.name = this.constructor.name, null === (t2 = Error.captureStackTrace) || void 0 === t2 || t2.call(Error, this, this.constructor);
  }
}
function L(e2) {
  switch (e2.algorithm.name) {
    case "RSA-PSS":
      return (function(e3) {
        if ("SHA-256" === e3.algorithm.hash.name) return "PS256";
        throw new A("unsupported RsaHashedKeyAlgorithm hash name");
      })(e2);
    case "RSASSA-PKCS1-v1_5":
      return (function(e3) {
        if ("SHA-256" === e3.algorithm.hash.name) return "RS256";
        throw new A("unsupported RsaHashedKeyAlgorithm hash name");
      })(e2);
    case "ECDSA":
      return (function(e3) {
        if ("P-256" === e3.algorithm.namedCurve) return "ES256";
        throw new A("unsupported EcKeyAlgorithm namedCurve");
      })(e2);
    case "Ed25519":
      return "Ed25519";
    default:
      throw new A("unsupported CryptoKey algorithm name");
  }
}
function Z(e2) {
  return e2 instanceof CryptoKey;
}
function H(e2) {
  return Z(e2) && "public" === e2.type;
}
async function W(e2, t2, o2, n2, i2, r2) {
  const s2 = null == e2 ? void 0 : e2.privateKey, a2 = null == e2 ? void 0 : e2.publicKey;
  if (!Z(c2 = s2) || "private" !== c2.type) throw new TypeError('"keypair.privateKey" must be a private CryptoKey');
  var c2;
  if (!H(a2)) throw new TypeError('"keypair.publicKey" must be a public CryptoKey');
  if (true !== a2.extractable) throw new TypeError('"keypair.publicKey.extractable" must be true');
  if ("string" != typeof t2) throw new TypeError('"htu" must be a string');
  if ("string" != typeof o2) throw new TypeError('"htm" must be a string');
  if (void 0 !== n2 && "string" != typeof n2) throw new TypeError('"nonce" must be a string or undefined');
  if (void 0 !== i2 && "string" != typeof i2) throw new TypeError('"accessToken" must be a string or undefined');
  return N({ alg: L(s2), typ: "dpop+jwt", jwk: await J(a2) }, Object.assign(Object.assign({}, r2), { iat: Math.floor(Date.now() / 1e3), jti: crypto.randomUUID(), htm: o2, nonce: n2, htu: t2, ath: i2 ? D(await crypto.subtle.digest("SHA-256", z(i2))) : void 0 }), s2);
}
async function J(e2) {
  const { kty: t2, e: o2, n: n2, x: i2, y: r2, crv: s2 } = await crypto.subtle.exportKey("jwk", e2);
  return { kty: t2, crv: s2, e: o2, n: n2, x: i2, y: r2 };
}
const X = ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:token-exchange"];
function V() {
  return (async function(e2, t2) {
    var o2;
    let n2;
    if (0 === e2.length) throw new TypeError('"alg" must be a non-empty string');
    switch (e2) {
      case "PS256":
        n2 = { name: "RSA-PSS", hash: "SHA-256", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]) };
        break;
      case "RS256":
        n2 = { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]) };
        break;
      case "ES256":
        n2 = { name: "ECDSA", namedCurve: "P-256" };
        break;
      case "Ed25519":
        n2 = { name: "Ed25519" };
        break;
      default:
        throw new A();
    }
    return crypto.subtle.generateKey(n2, null !== (o2 = null == t2 ? void 0 : t2.extractable) && void 0 !== o2 && o2, ["sign", "verify"]);
  })("ES256", { extractable: false });
}
function F(e2) {
  return (async function(e3) {
    if (!H(e3)) throw new TypeError('"publicKey" must be a public CryptoKey');
    if (true !== e3.extractable) throw new TypeError('"publicKey.extractable" must be true');
    const t2 = await J(e3);
    let o2;
    switch (t2.kty) {
      case "EC":
        o2 = { crv: t2.crv, kty: t2.kty, x: t2.x, y: t2.y };
        break;
      case "OKP":
        o2 = { crv: t2.crv, kty: t2.kty, x: t2.x };
        break;
      case "RSA":
        o2 = { e: t2.e, kty: t2.kty, n: t2.n };
        break;
      default:
        throw new A("unsupported JWK kty");
    }
    return D(await crypto.subtle.digest({ name: "SHA-256" }, z(JSON.stringify(o2))));
  })(e2.publicKey);
}
function G({ keyPair: e2, url: t2, method: o2, nonce: n2, accessToken: i2 }) {
  const r2 = (function(e3) {
    const t3 = new URL(e3);
    return t3.search = "", t3.hash = "", t3.href;
  })(t2);
  return W(e2, r2, o2, n2, i2);
}
const M = async (e2, t2) => {
  const o2 = await fetch(e2, t2);
  return { ok: o2.ok, json: await o2.json(), headers: (n2 = o2.headers, [...n2].reduce(((e3, [t3, o3]) => (e3[t3] = o3, e3)), {})) };
  var n2;
}, Y = async (e2, t2, o2) => {
  const n2 = new AbortController();
  let i2;
  return t2.signal = n2.signal, Promise.race([M(e2, t2), new Promise(((e3, t3) => {
    i2 = setTimeout((() => {
      n2.abort(), t3(new Error("Timeout when executing 'fetch'"));
    }), o2);
  }))]).finally((() => {
    clearTimeout(i2);
  }));
}, $ = async (e2, t2, o2, n2, i2, r2, s2, a2) => {
  return c2 = { auth: { audience: t2, scope: o2 }, timeout: i2, fetchUrl: e2, fetchOptions: n2, useFormData: s2, useMrrt: a2 }, u2 = r2, new Promise((function(e3, t3) {
    const o3 = new MessageChannel();
    o3.port1.onmessage = function(n3) {
      n3.data.error ? t3(new Error(n3.data.error)) : e3(n3.data), o3.port1.close();
    }, u2.postMessage(c2, [o3.port2]);
  }));
  var c2, u2;
}, B = async (e2, t2, o2, n2, i2, r2, s2 = 1e4, a2) => i2 ? $(e2, t2, o2, n2, s2, i2, r2, a2) : Y(e2, n2, s2);
async function q(t2, o2, n2, i2, r2, s2, a2, c2, d2, h2) {
  if (d2) {
    const e2 = await d2.generateProof({ url: t2, method: r2.method || "GET", nonce: await d2.getNonce() });
    r2.headers = Object.assign(Object.assign({}, r2.headers), { dpop: e2 });
  }
  let l2, p2 = null;
  for (let e2 = 0; e2 < 3; e2++) try {
    l2 = await B(t2, n2, i2, r2, s2, a2, o2, c2), p2 = null;
    break;
  } catch (e3) {
    p2 = e3;
  }
  if (p2) throw p2;
  const m2 = l2.json, { error: f2, error_description: w2 } = m2, k2 = e(m2, ["error", "error_description"]), { headers: v2, ok: _2 } = l2;
  let S2;
  if (d2 && (S2 = v2["dpop-nonce"], S2 && await d2.setNonce(S2)), !_2) {
    const e2 = w2 || `HTTP error. Unable to fetch ${t2}`;
    if ("mfa_required" === f2) throw new g(f2, e2, k2.mfa_token);
    if ("missing_refresh_token" === f2) throw new y(n2, i2);
    if ("use_dpop_nonce" === f2) {
      if (!d2 || !S2 || h2) throw new b(S2);
      return q(t2, o2, n2, i2, r2, s2, a2, c2, d2, true);
    }
    throw new u(f2 || "request_error", e2);
  }
  return k2;
}
async function Q(t2, o2) {
  var { baseUrl: n2, timeout: i2, audience: r2, scope: s2, auth0Client: c2, useFormData: u2, useMrrt: d2, dpop: h2 } = t2, l2 = e(t2, ["baseUrl", "timeout", "audience", "scope", "auth0Client", "useFormData", "useMrrt", "dpop"]);
  const p2 = "urn:ietf:params:oauth:grant-type:token-exchange" === l2.grant_type, m2 = "refresh_token" === l2.grant_type && d2, f2 = Object.assign(Object.assign(Object.assign(Object.assign({}, l2), p2 && r2 && { audience: r2 }), p2 && s2 && { scope: s2 }), m2 && { audience: r2, scope: s2 }), g2 = u2 ? T(f2) : JSON.stringify(f2), y2 = (w2 = l2.grant_type, X.includes(w2));
  var w2;
  return await q(`${n2}/oauth/token`, i2, r2 || "default", s2, { method: "POST", body: g2, headers: { "Content-Type": u2 ? "application/x-www-form-urlencoded" : "application/json", "Auth0-Client": btoa(JSON.stringify(P(c2 || a))) } }, o2, u2, d2, y2 ? h2 : void 0);
}
const ee = (...e2) => {
  return (t2 = e2.filter(Boolean).join(" ").trim().split(/\s+/), Array.from(new Set(t2))).join(" ");
  var t2;
}, te = (e2, t2, o2) => {
  let n2;
  return o2 && (n2 = e2[o2]), n2 || (n2 = e2.default), ee(n2, t2);
};
class oe {
  constructor(e2, t2 = "@@auth0spajs@@", o2) {
    this.prefix = t2, this.suffix = o2, this.clientId = e2.clientId, this.scope = e2.scope, this.audience = e2.audience;
  }
  toKey() {
    return [this.prefix, this.clientId, this.audience, this.scope, this.suffix].filter(Boolean).join("::");
  }
  static fromKey(e2) {
    const [t2, o2, n2, i2] = e2.split("::");
    return new oe({ clientId: o2, scope: i2, audience: n2 }, t2);
  }
  static fromCacheEntry(e2) {
    const { scope: t2, audience: o2, client_id: n2 } = e2;
    return new oe({ scope: t2, audience: o2, clientId: n2 });
  }
}
class ne {
  set(e2, t2) {
    localStorage.setItem(e2, JSON.stringify(t2));
  }
  get(e2) {
    const t2 = window.localStorage.getItem(e2);
    if (t2) try {
      return JSON.parse(t2);
    } catch (e3) {
      return;
    }
  }
  remove(e2) {
    localStorage.removeItem(e2);
  }
  allKeys() {
    return Object.keys(window.localStorage).filter(((e2) => e2.startsWith("@@auth0spajs@@")));
  }
}
class ie {
  constructor() {
    this.enclosedCache = /* @__PURE__ */ (function() {
      let e2 = {};
      return { set(t2, o2) {
        e2[t2] = o2;
      }, get(t2) {
        const o2 = e2[t2];
        if (o2) return o2;
      }, remove(t2) {
        delete e2[t2];
      }, allKeys: () => Object.keys(e2) };
    })();
  }
}
class re {
  constructor(e2, t2, o2) {
    this.cache = e2, this.keyManifest = t2, this.nowProvider = o2 || c;
  }
  async setIdToken(e2, t2, o2) {
    var n2;
    const i2 = this.getIdTokenCacheKey(e2);
    await this.cache.set(i2, { id_token: t2, decodedToken: o2 }), await (null === (n2 = this.keyManifest) || void 0 === n2 ? void 0 : n2.add(i2));
  }
  async getIdToken(e2) {
    const t2 = await this.cache.get(this.getIdTokenCacheKey(e2.clientId));
    if (!t2 && e2.scope && e2.audience) {
      const t3 = await this.get(e2);
      if (!t3) return;
      if (!t3.id_token || !t3.decodedToken) return;
      return { id_token: t3.id_token, decodedToken: t3.decodedToken };
    }
    if (t2) return { id_token: t2.id_token, decodedToken: t2.decodedToken };
  }
  async get(e2, t2 = 0, o2 = false, n2) {
    var i2;
    let r2 = await this.cache.get(e2.toKey());
    if (!r2) {
      const t3 = await this.getCacheKeys();
      if (!t3) return;
      const i3 = this.matchExistingCacheKey(e2, t3);
      if (i3 && (r2 = await this.cache.get(i3)), !i3 && o2 && "cache-only" !== n2) return this.getEntryWithRefreshToken(e2, t3);
    }
    if (!r2) return;
    const s2 = await this.nowProvider(), a2 = Math.floor(s2 / 1e3);
    return r2.expiresAt - t2 < a2 ? r2.body.refresh_token ? this.modifiedCachedEntry(r2, e2) : (await this.cache.remove(e2.toKey()), void await (null === (i2 = this.keyManifest) || void 0 === i2 ? void 0 : i2.remove(e2.toKey()))) : r2.body;
  }
  async modifiedCachedEntry(e2, t2) {
    return e2.body = { refresh_token: e2.body.refresh_token, audience: e2.body.audience, scope: e2.body.scope }, await this.cache.set(t2.toKey(), e2), { refresh_token: e2.body.refresh_token, audience: e2.body.audience, scope: e2.body.scope };
  }
  async set(e2) {
    var t2;
    const o2 = new oe({ clientId: e2.client_id, scope: e2.scope, audience: e2.audience }), n2 = await this.wrapCacheEntry(e2);
    await this.cache.set(o2.toKey(), n2), await (null === (t2 = this.keyManifest) || void 0 === t2 ? void 0 : t2.add(o2.toKey()));
  }
  async remove(e2, t2, o2) {
    const n2 = new oe({ clientId: e2, scope: o2, audience: t2 });
    await this.cache.remove(n2.toKey());
  }
  async clear(e2) {
    var t2;
    const o2 = await this.getCacheKeys();
    o2 && (await o2.filter(((t3) => !e2 || t3.includes(e2))).reduce((async (e3, t3) => {
      await e3, await this.cache.remove(t3);
    }), Promise.resolve()), await (null === (t2 = this.keyManifest) || void 0 === t2 ? void 0 : t2.clear()));
  }
  async wrapCacheEntry(e2) {
    const t2 = await this.nowProvider();
    return { body: e2, expiresAt: Math.floor(t2 / 1e3) + e2.expires_in };
  }
  async getCacheKeys() {
    var e2;
    return this.keyManifest ? null === (e2 = await this.keyManifest.get()) || void 0 === e2 ? void 0 : e2.keys : this.cache.allKeys ? this.cache.allKeys() : void 0;
  }
  getIdTokenCacheKey(e2) {
    return new oe({ clientId: e2 }, "@@auth0spajs@@", "@@user@@").toKey();
  }
  matchExistingCacheKey(e2, t2) {
    return t2.filter(((t3) => {
      var o2;
      const n2 = oe.fromKey(t3), i2 = new Set(n2.scope && n2.scope.split(" ")), r2 = (null === (o2 = e2.scope) || void 0 === o2 ? void 0 : o2.split(" ")) || [], s2 = n2.scope && r2.reduce(((e3, t4) => e3 && i2.has(t4)), true);
      return "@@auth0spajs@@" === n2.prefix && n2.clientId === e2.clientId && n2.audience === e2.audience && s2;
    }))[0];
  }
  async getEntryWithRefreshToken(e2, t2) {
    var o2;
    for (const n2 of t2) {
      const t3 = oe.fromKey(n2);
      if ("@@auth0spajs@@" === t3.prefix && t3.clientId === e2.clientId) {
        const t4 = await this.cache.get(n2);
        if (null === (o2 = null == t4 ? void 0 : t4.body) || void 0 === o2 ? void 0 : o2.refresh_token) return this.modifiedCachedEntry(t4, e2);
      }
    }
  }
  async updateEntry(e2, t2) {
    var o2;
    const n2 = await this.getCacheKeys();
    if (n2) for (const i2 of n2) {
      const n3 = await this.cache.get(i2);
      if ((null === (o2 = null == n3 ? void 0 : n3.body) || void 0 === o2 ? void 0 : o2.refresh_token) === e2) {
        const e3 = Object.assign(Object.assign({}, n3.body), { refresh_token: t2 });
        await this.set(e3);
      }
    }
  }
}
class se {
  constructor(e2, t2, o2) {
    this.storage = e2, this.clientId = t2, this.cookieDomain = o2, this.storageKey = `a0.spajs.txs.${this.clientId}`;
  }
  create(e2) {
    this.storage.save(this.storageKey, e2, { daysUntilExpire: 1, cookieDomain: this.cookieDomain });
  }
  get() {
    return this.storage.get(this.storageKey);
  }
  remove() {
    this.storage.remove(this.storageKey, { cookieDomain: this.cookieDomain });
  }
}
const ae = (e2) => "number" == typeof e2, ce = ["iss", "aud", "exp", "nbf", "iat", "jti", "azp", "nonce", "auth_time", "at_hash", "c_hash", "acr", "amr", "sub_jwk", "cnf", "sip_from_tag", "sip_date", "sip_callid", "sip_cseq_num", "sip_via_branch", "orig", "dest", "mky", "events", "toe", "txn", "rph", "sid", "vot", "vtm"], ue = (e2) => {
  if (!e2.id_token) throw new Error("ID token is required but missing");
  const t2 = ((e3) => {
    const t3 = e3.split("."), [o3, n3, i3] = t3;
    if (3 !== t3.length || !o3 || !n3 || !i3) throw new Error("ID token could not be decoded");
    const r2 = JSON.parse(j(n3)), s2 = { __raw: e3 }, a2 = {};
    return Object.keys(r2).forEach(((e4) => {
      s2[e4] = r2[e4], ce.includes(e4) || (a2[e4] = r2[e4]);
    })), { encoded: { header: o3, payload: n3, signature: i3 }, header: JSON.parse(j(o3)), claims: s2, user: a2 };
  })(e2.id_token);
  if (!t2.claims.iss) throw new Error("Issuer (iss) claim must be a string present in the ID token");
  if (t2.claims.iss !== e2.iss) throw new Error(`Issuer (iss) claim mismatch in the ID token; expected "${e2.iss}", found "${t2.claims.iss}"`);
  if (!t2.user.sub) throw new Error("Subject (sub) claim must be a string present in the ID token");
  if ("RS256" !== t2.header.alg) throw new Error(`Signature algorithm of "${t2.header.alg}" is not supported. Expected the ID token to be signed with "RS256".`);
  if (!t2.claims.aud || "string" != typeof t2.claims.aud && !Array.isArray(t2.claims.aud)) throw new Error("Audience (aud) claim must be a string or array of strings present in the ID token");
  if (Array.isArray(t2.claims.aud)) {
    if (!t2.claims.aud.includes(e2.aud)) throw new Error(`Audience (aud) claim mismatch in the ID token; expected "${e2.aud}" but was not one of "${t2.claims.aud.join(", ")}"`);
    if (t2.claims.aud.length > 1) {
      if (!t2.claims.azp) throw new Error("Authorized Party (azp) claim must be a string present in the ID token when Audience (aud) claim has multiple values");
      if (t2.claims.azp !== e2.aud) throw new Error(`Authorized Party (azp) claim mismatch in the ID token; expected "${e2.aud}", found "${t2.claims.azp}"`);
    }
  } else if (t2.claims.aud !== e2.aud) throw new Error(`Audience (aud) claim mismatch in the ID token; expected "${e2.aud}" but found "${t2.claims.aud}"`);
  if (e2.nonce) {
    if (!t2.claims.nonce) throw new Error("Nonce (nonce) claim must be a string present in the ID token");
    if (t2.claims.nonce !== e2.nonce) throw new Error(`Nonce (nonce) claim mismatch in the ID token; expected "${e2.nonce}", found "${t2.claims.nonce}"`);
  }
  if (e2.max_age && !ae(t2.claims.auth_time)) throw new Error("Authentication Time (auth_time) claim must be a number present in the ID token when Max Age (max_age) is specified");
  if (null == t2.claims.exp || !ae(t2.claims.exp)) throw new Error("Expiration Time (exp) claim must be a number present in the ID token");
  if (!ae(t2.claims.iat)) throw new Error("Issued At (iat) claim must be a number present in the ID token");
  const o2 = e2.leeway || 60, n2 = new Date(e2.now || Date.now()), i2 = /* @__PURE__ */ new Date(0);
  if (i2.setUTCSeconds(t2.claims.exp + o2), n2 > i2) throw new Error(`Expiration Time (exp) claim error in the ID token; current time (${n2}) is after expiration time (${i2})`);
  if (null != t2.claims.nbf && ae(t2.claims.nbf)) {
    const e3 = /* @__PURE__ */ new Date(0);
    if (e3.setUTCSeconds(t2.claims.nbf - o2), n2 < e3) throw new Error(`Not Before time (nbf) claim in the ID token indicates that this token can't be used just yet. Current time (${n2}) is before ${e3}`);
  }
  if (null != t2.claims.auth_time && ae(t2.claims.auth_time)) {
    const i3 = /* @__PURE__ */ new Date(0);
    if (i3.setUTCSeconds(parseInt(t2.claims.auth_time) + e2.max_age + o2), n2 > i3) throw new Error(`Authentication Time (auth_time) claim in the ID token indicates that too much time has passed since the last end-user authentication. Current time (${n2}) is after last auth at ${i3}`);
  }
  if (e2.organization) {
    const o3 = e2.organization.trim();
    if (o3.startsWith("org_")) {
      const e3 = o3;
      if (!t2.claims.org_id) throw new Error("Organization ID (org_id) claim must be a string present in the ID token");
      if (e3 !== t2.claims.org_id) throw new Error(`Organization ID (org_id) claim mismatch in the ID token; expected "${e3}", found "${t2.claims.org_id}"`);
    } else {
      const e3 = o3.toLowerCase();
      if (!t2.claims.org_name) throw new Error("Organization Name (org_name) claim must be a string present in the ID token");
      if (e3 !== t2.claims.org_name) throw new Error(`Organization Name (org_name) claim mismatch in the ID token; expected "${e3}", found "${t2.claims.org_name}"`);
    }
  }
  return t2;
};
var de = n((function(e2, o2) {
  var n2 = t && t.__assign || function() {
    return n2 = Object.assign || function(e3) {
      for (var t2, o3 = 1, n3 = arguments.length; o3 < n3; o3++) for (var i3 in t2 = arguments[o3]) Object.prototype.hasOwnProperty.call(t2, i3) && (e3[i3] = t2[i3]);
      return e3;
    }, n2.apply(this, arguments);
  };
  function i2(e3, t2) {
    if (!t2) return "";
    var o3 = "; " + e3;
    return true === t2 ? o3 : o3 + "=" + t2;
  }
  function r2(e3, t2, o3) {
    return encodeURIComponent(e3).replace(/%(23|24|26|2B|5E|60|7C)/g, decodeURIComponent).replace(/\(/g, "%28").replace(/\)/g, "%29") + "=" + encodeURIComponent(t2).replace(/%(23|24|26|2B|3A|3C|3E|3D|2F|3F|40|5B|5D|5E|60|7B|7D|7C)/g, decodeURIComponent) + (function(e4) {
      if ("number" == typeof e4.expires) {
        var t3 = /* @__PURE__ */ new Date();
        t3.setMilliseconds(t3.getMilliseconds() + 864e5 * e4.expires), e4.expires = t3;
      }
      return i2("Expires", e4.expires ? e4.expires.toUTCString() : "") + i2("Domain", e4.domain) + i2("Path", e4.path) + i2("Secure", e4.secure) + i2("SameSite", e4.sameSite);
    })(o3);
  }
  function s2(e3) {
    for (var t2 = {}, o3 = e3 ? e3.split("; ") : [], n3 = /(%[\dA-F]{2})+/gi, i3 = 0; i3 < o3.length; i3++) {
      var r3 = o3[i3].split("="), s3 = r3.slice(1).join("=");
      '"' === s3.charAt(0) && (s3 = s3.slice(1, -1));
      try {
        t2[r3[0].replace(n3, decodeURIComponent)] = s3.replace(n3, decodeURIComponent);
      } catch (e4) {
      }
    }
    return t2;
  }
  function a2() {
    return s2(document.cookie);
  }
  function c2(e3, t2, o3) {
    document.cookie = r2(e3, t2, n2({ path: "/" }, o3));
  }
  o2.__esModule = true, o2.encode = r2, o2.parse = s2, o2.getAll = a2, o2.get = function(e3) {
    return a2()[e3];
  }, o2.set = c2, o2.remove = function(e3, t2) {
    c2(e3, "", n2(n2({}, t2), { expires: -1 }));
  };
}));
o(de), de.encode, de.parse, de.getAll;
var he = de.get, le = de.set, pe = de.remove;
const me = { get(e2) {
  const t2 = he(e2);
  if (void 0 !== t2) return JSON.parse(t2);
}, save(e2, t2, o2) {
  let n2 = {};
  "https:" === window.location.protocol && (n2 = { secure: true, sameSite: "none" }), (null == o2 ? void 0 : o2.daysUntilExpire) && (n2.expires = o2.daysUntilExpire), (null == o2 ? void 0 : o2.cookieDomain) && (n2.domain = o2.cookieDomain), le(e2, JSON.stringify(t2), n2);
}, remove(e2, t2) {
  let o2 = {};
  (null == t2 ? void 0 : t2.cookieDomain) && (o2.domain = t2.cookieDomain), pe(e2, o2);
} }, fe = { get(e2) {
  const t2 = me.get(e2);
  return t2 || me.get(`_legacy_${e2}`);
}, save(e2, t2, o2) {
  let n2 = {};
  "https:" === window.location.protocol && (n2 = { secure: true }), (null == o2 ? void 0 : o2.daysUntilExpire) && (n2.expires = o2.daysUntilExpire), (null == o2 ? void 0 : o2.cookieDomain) && (n2.domain = o2.cookieDomain), le(`_legacy_${e2}`, JSON.stringify(t2), n2), me.save(e2, t2, o2);
}, remove(e2, t2) {
  let o2 = {};
  (null == t2 ? void 0 : t2.cookieDomain) && (o2.domain = t2.cookieDomain), pe(e2, o2), me.remove(e2, t2), me.remove(`_legacy_${e2}`, t2);
} }, ge = { get(e2) {
  if ("undefined" == typeof sessionStorage) return;
  const t2 = sessionStorage.getItem(e2);
  return null != t2 ? JSON.parse(t2) : void 0;
}, save(e2, t2) {
  sessionStorage.setItem(e2, JSON.stringify(t2));
}, remove(e2) {
  sessionStorage.removeItem(e2);
} };
var ye;
!(function(e2) {
  e2.Code = "code", e2.ConnectCode = "connect_code";
})(ye || (ye = {}));
function be(e2, t2, o2) {
  var n2 = void 0 === t2 ? null : t2, i2 = (function(e3, t3) {
    var o3 = atob(e3);
    if (t3) {
      for (var n3 = new Uint8Array(o3.length), i3 = 0, r3 = o3.length; i3 < r3; ++i3) n3[i3] = o3.charCodeAt(i3);
      return String.fromCharCode.apply(null, new Uint16Array(n3.buffer));
    }
    return o3;
  })(e2, void 0 !== o2 && o2), r2 = i2.indexOf("\n", 10) + 1, s2 = i2.substring(r2) + (n2 ? "//# sourceMappingURL=" + n2 : ""), a2 = new Blob([s2], { type: "application/javascript" });
  return URL.createObjectURL(a2);
}
var ke, ve, _e, Se, Ie = (ke = "Lyogcm9sbHVwLXBsdWdpbi13ZWItd29ya2VyLWxvYWRlciAqLwohZnVuY3Rpb24oKXsidXNlIHN0cmljdCI7Y2xhc3MgZSBleHRlbmRzIEVycm9ye2NvbnN0cnVjdG9yKHQscil7c3VwZXIociksdGhpcy5lcnJvcj10LHRoaXMuZXJyb3JfZGVzY3JpcHRpb249cixPYmplY3Quc2V0UHJvdG90eXBlT2YodGhpcyxlLnByb3RvdHlwZSl9c3RhdGljIGZyb21QYXlsb2FkKHtlcnJvcjp0LGVycm9yX2Rlc2NyaXB0aW9uOnJ9KXtyZXR1cm4gbmV3IGUodCxyKX19Y2xhc3MgdCBleHRlbmRzIGV7Y29uc3RydWN0b3IoZSxzKXtzdXBlcigibWlzc2luZ19yZWZyZXNoX3Rva2VuIixgTWlzc2luZyBSZWZyZXNoIFRva2VuIChhdWRpZW5jZTogJyR7cihlLFsiZGVmYXVsdCJdKX0nLCBzY29wZTogJyR7cihzKX0nKWApLHRoaXMuYXVkaWVuY2U9ZSx0aGlzLnNjb3BlPXMsT2JqZWN0LnNldFByb3RvdHlwZU9mKHRoaXMsdC5wcm90b3R5cGUpfX1mdW5jdGlvbiByKGUsdD1bXSl7cmV0dXJuIGUmJiF0LmluY2x1ZGVzKGUpP2U6IiJ9ImZ1bmN0aW9uIj09dHlwZW9mIFN1cHByZXNzZWRFcnJvciYmU3VwcHJlc3NlZEVycm9yO2NvbnN0IHM9ZT0+e3ZhcntjbGllbnRJZDp0fT1lLHI9ZnVuY3Rpb24oZSx0KXt2YXIgcj17fTtmb3IodmFyIHMgaW4gZSlPYmplY3QucHJvdG90eXBlLmhhc093blByb3BlcnR5LmNhbGwoZSxzKSYmdC5pbmRleE9mKHMpPDAmJihyW3NdPWVbc10pO2lmKG51bGwhPWUmJiJmdW5jdGlvbiI9PXR5cGVvZiBPYmplY3QuZ2V0T3duUHJvcGVydHlTeW1ib2xzKXt2YXIgbz0wO2ZvcihzPU9iamVjdC5nZXRPd25Qcm9wZXJ0eVN5bWJvbHMoZSk7bzxzLmxlbmd0aDtvKyspdC5pbmRleE9mKHNbb10pPDAmJk9iamVjdC5wcm90b3R5cGUucHJvcGVydHlJc0VudW1lcmFibGUuY2FsbChlLHNbb10pJiYocltzW29dXT1lW3Nbb11dKX1yZXR1cm4gcn0oZSxbImNsaWVudElkIl0pO3JldHVybiBuZXcgVVJMU2VhcmNoUGFyYW1zKChlPT5PYmplY3Qua2V5cyhlKS5maWx0ZXIoKHQ9PnZvaWQgMCE9PWVbdF0pKS5yZWR1Y2UoKCh0LHIpPT5PYmplY3QuYXNzaWduKE9iamVjdC5hc3NpZ24oe30sdCkse1tyXTplW3JdfSkpLHt9KSkoT2JqZWN0LmFzc2lnbih7Y2xpZW50X2lkOnR9LHIpKSkudG9TdHJpbmcoKX07bGV0IG89e307Y29uc3Qgbj0oZSx0KT0+YCR7ZX18JHt0fWA7YWRkRXZlbnRMaXN0ZW5lcigibWVzc2FnZSIsKGFzeW5jKHtkYXRhOnt0aW1lb3V0OmUsYXV0aDpyLGZldGNoVXJsOmksZmV0Y2hPcHRpb25zOmMsdXNlRm9ybURhdGE6YSx1c2VNcnJ0OmZ9LHBvcnRzOltwXX0pPT57bGV0IGgsdSxsPXt9O2NvbnN0e2F1ZGllbmNlOmQsc2NvcGU6eX09cnx8e307dHJ5e2NvbnN0IHI9YT8oZT0+e2NvbnN0IHQ9bmV3IFVSTFNlYXJjaFBhcmFtcyhlKSxyPXt9O3JldHVybiB0LmZvckVhY2goKChlLHQpPT57clt0XT1lfSkpLHJ9KShjLmJvZHkpOkpTT04ucGFyc2UoYy5ib2R5KTtpZighci5yZWZyZXNoX3Rva2VuJiYicmVmcmVzaF90b2tlbiI9PT1yLmdyYW50X3R5cGUpe2lmKHU9KChlLHQpPT5vW24oZSx0KV0pKGQseSksIXUmJmYpe2NvbnN0IGU9by5sYXRlc3RfcmVmcmVzaF90b2tlbix0PSgoZSx0KT0+e2NvbnN0IHI9T2JqZWN0LmtleXMobykuZmluZCgocj0+e2lmKCJsYXRlc3RfcmVmcmVzaF90b2tlbiIhPT1yKXtjb25zdCBzPSgoZSx0KT0+dC5zdGFydHNXaXRoKGAke2V9fGApKSh0LHIpLG89ci5zcGxpdCgifCIpWzFdLnNwbGl0KCIgIiksbj1lLnNwbGl0KCIgIikuZXZlcnkoKGU9Pm8uaW5jbHVkZXMoZSkpKTtyZXR1cm4gcyYmbn19KSk7cmV0dXJuISFyfSkoeSxkKTtlJiYhdCYmKHU9ZSl9aWYoIXUpdGhyb3cgbmV3IHQoZCx5KTtjLmJvZHk9YT9zKE9iamVjdC5hc3NpZ24oT2JqZWN0LmFzc2lnbih7fSxyKSx7cmVmcmVzaF90b2tlbjp1fSkpOkpTT04uc3RyaW5naWZ5KE9iamVjdC5hc3NpZ24oT2JqZWN0LmFzc2lnbih7fSxyKSx7cmVmcmVzaF90b2tlbjp1fSkpfWxldCBqLGs7ImZ1bmN0aW9uIj09dHlwZW9mIEFib3J0Q29udHJvbGxlciYmKGo9bmV3IEFib3J0Q29udHJvbGxlcixjLnNpZ25hbD1qLnNpZ25hbCk7dHJ5e2s9YXdhaXQgUHJvbWlzZS5yYWNlKFsoXz1lLG5ldyBQcm9taXNlKChlPT5zZXRUaW1lb3V0KGUsXykpKSksZmV0Y2goaSxPYmplY3QuYXNzaWduKHt9LGMpKV0pfWNhdGNoKGUpe3JldHVybiB2b2lkIHAucG9zdE1lc3NhZ2Uoe2Vycm9yOmUubWVzc2FnZX0pfWlmKCFrKXJldHVybiBqJiZqLmFib3J0KCksdm9pZCBwLnBvc3RNZXNzYWdlKHtlcnJvcjoiVGltZW91dCB3aGVuIGV4ZWN1dGluZyAnZmV0Y2gnIn0pO2c9ay5oZWFkZXJzLGw9Wy4uLmddLnJlZHVjZSgoKGUsW3Qscl0pPT4oZVt0XT1yLGUpKSx7fSksaD1hd2FpdCBrLmpzb24oKSxoLnJlZnJlc2hfdG9rZW4/KGYmJihvLmxhdGVzdF9yZWZyZXNoX3Rva2VuPWgucmVmcmVzaF90b2tlbixPPXUsYj1oLnJlZnJlc2hfdG9rZW4sT2JqZWN0LmVudHJpZXMobykuZm9yRWFjaCgoKFtlLHRdKT0+e3Q9PT1PJiYob1tlXT1iKX0pKSksKChlLHQscik9PntvW24odCxyKV09ZX0pKGgucmVmcmVzaF90b2tlbixkLHkpLGRlbGV0ZSBoLnJlZnJlc2hfdG9rZW4pOigoZSx0KT0+e2RlbGV0ZSBvW24oZSx0KV19KShkLHkpLHAucG9zdE1lc3NhZ2Uoe29rOmsub2ssanNvbjpoLGhlYWRlcnM6bH0pfWNhdGNoKGUpe3AucG9zdE1lc3NhZ2Uoe29rOiExLGpzb246e2Vycm9yOmUuZXJyb3IsZXJyb3JfZGVzY3JpcHRpb246ZS5tZXNzYWdlfSxoZWFkZXJzOmx9KX12YXIgTyxiLGcsX30pKX0oKTsKCg==", ve = null, _e = false, function(e2) {
  return Se = Se || be(ke, ve, _e), new Worker(Se, e2);
});
const Pe = {};
class Te {
  constructor(e2, t2) {
    this.cache = e2, this.clientId = t2, this.manifestKey = this.createManifestKeyFrom(this.clientId);
  }
  async add(e2) {
    var t2;
    const o2 = new Set((null === (t2 = await this.cache.get(this.manifestKey)) || void 0 === t2 ? void 0 : t2.keys) || []);
    o2.add(e2), await this.cache.set(this.manifestKey, { keys: [...o2] });
  }
  async remove(e2) {
    const t2 = await this.cache.get(this.manifestKey);
    if (t2) {
      const o2 = new Set(t2.keys);
      return o2.delete(e2), o2.size > 0 ? await this.cache.set(this.manifestKey, { keys: [...o2] }) : await this.cache.remove(this.manifestKey);
    }
  }
  get() {
    return this.cache.get(this.manifestKey);
  }
  clear() {
    return this.cache.remove(this.manifestKey);
  }
  createManifestKeyFrom(e2) {
    return `@@auth0spajs@@::${e2}`;
  }
}
const Oe = { memory: () => new ie().enclosedCache, localstorage: () => new ne() }, je = (e2) => Oe[e2], Ce = (t2) => {
  const { openUrl: o2, onRedirect: n2 } = t2, i2 = e(t2, ["openUrl", "onRedirect"]);
  return Object.assign(Object.assign({}, i2), { openUrl: false === o2 || o2 ? o2 : n2 });
}, Ke = (e2, t2) => {
  const o2 = (null == t2 ? void 0 : t2.split(" ")) || [];
  return ((null == e2 ? void 0 : e2.split(" ")) || []).every(((e3) => o2.includes(e3)));
}, xe = { NONCE: "nonce", KEYPAIR: "keypair" };
class ze {
  constructor(e2) {
    this.clientId = e2;
  }
  getVersion() {
    return 1;
  }
  createDbHandle() {
    const e2 = window.indexedDB.open("auth0-spa-js", this.getVersion());
    return new Promise(((t2, o2) => {
      e2.onupgradeneeded = () => Object.values(xe).forEach(((t3) => e2.result.createObjectStore(t3))), e2.onerror = () => o2(e2.error), e2.onsuccess = () => t2(e2.result);
    }));
  }
  async getDbHandle() {
    return this.dbHandle || (this.dbHandle = await this.createDbHandle()), this.dbHandle;
  }
  async executeDbRequest(e2, t2, o2) {
    const n2 = o2((await this.getDbHandle()).transaction(e2, t2).objectStore(e2));
    return new Promise(((e3, t3) => {
      n2.onsuccess = () => e3(n2.result), n2.onerror = () => t3(n2.error);
    }));
  }
  buildKey(e2) {
    const t2 = e2 ? `_${e2}` : "auth0";
    return `${this.clientId}::${t2}`;
  }
  setNonce(e2, t2) {
    return this.save(xe.NONCE, this.buildKey(t2), e2);
  }
  setKeyPair(e2) {
    return this.save(xe.KEYPAIR, this.buildKey(), e2);
  }
  async save(e2, t2, o2) {
    await this.executeDbRequest(e2, "readwrite", ((e3) => e3.put(o2, t2)));
  }
  findNonce(e2) {
    return this.find(xe.NONCE, this.buildKey(e2));
  }
  findKeyPair() {
    return this.find(xe.KEYPAIR, this.buildKey());
  }
  find(e2, t2) {
    return this.executeDbRequest(e2, "readonly", ((e3) => e3.get(t2)));
  }
  async deleteBy(e2, t2) {
    const o2 = await this.executeDbRequest(e2, "readonly", ((e3) => e3.getAllKeys()));
    null == o2 || o2.filter(t2).map(((t3) => this.executeDbRequest(e2, "readwrite", ((e3) => e3.delete(t3)))));
  }
  deleteByClientId(e2, t2) {
    return this.deleteBy(e2, ((e3) => "string" == typeof e3 && e3.startsWith(`${t2}::`)));
  }
  clearNonces() {
    return this.deleteByClientId(xe.NONCE, this.clientId);
  }
  clearKeyPairs() {
    return this.deleteByClientId(xe.KEYPAIR, this.clientId);
  }
}
class Ee {
  constructor(e2) {
    this.storage = new ze(e2);
  }
  getNonce(e2) {
    return this.storage.findNonce(e2);
  }
  setNonce(e2, t2) {
    return this.storage.setNonce(e2, t2);
  }
  async getOrGenerateKeyPair() {
    let e2 = await this.storage.findKeyPair();
    return e2 || (e2 = await V(), await this.storage.setKeyPair(e2)), e2;
  }
  async generateProof(e2) {
    const t2 = await this.getOrGenerateKeyPair();
    return G(Object.assign({ keyPair: t2 }, e2));
  }
  async calculateThumbprint() {
    return F(await this.getOrGenerateKeyPair());
  }
  async clear() {
    await Promise.all([this.storage.clearNonces(), this.storage.clearKeyPairs()]);
  }
}
var Ne;
!(function(e2) {
  e2.Bearer = "Bearer", e2.DPoP = "DPoP";
})(Ne || (Ne = {}));
class Re {
  constructor(e2, t2) {
    this.hooks = t2, this.config = Object.assign(Object.assign({}, e2), { fetch: e2.fetch || ("undefined" == typeof window ? fetch : window.fetch.bind(window)) });
  }
  isAbsoluteUrl(e2) {
    return /^(https?:)?\/\//i.test(e2);
  }
  buildUrl(e2, t2) {
    if (t2) {
      if (this.isAbsoluteUrl(t2)) return t2;
      if (e2) return `${e2.replace(/\/?\/$/, "")}/${t2.replace(/^\/+/, "")}`;
    }
    throw new TypeError("`url` must be absolute or `baseUrl` non-empty.");
  }
  getAccessToken(e2) {
    return this.config.getAccessToken ? this.config.getAccessToken(e2) : this.hooks.getAccessToken(e2);
  }
  extractUrl(e2) {
    return "string" == typeof e2 ? e2 : e2 instanceof URL ? e2.href : e2.url;
  }
  buildBaseRequest(e2, t2) {
    if (!this.config.baseUrl) return new Request(e2, t2);
    const o2 = this.buildUrl(this.config.baseUrl, this.extractUrl(e2)), n2 = e2 instanceof Request ? new Request(o2, e2) : o2;
    return new Request(n2, t2);
  }
  setAuthorizationHeader(e2, t2, o2 = Ne.Bearer) {
    e2.headers.set("authorization", `${o2} ${t2}`);
  }
  async setDpopProofHeader(e2, t2) {
    if (!this.config.dpopNonceId) return;
    const o2 = await this.hooks.getDpopNonce(), n2 = await this.hooks.generateDpopProof({ accessToken: t2, method: e2.method, nonce: o2, url: e2.url });
    e2.headers.set("dpop", n2);
  }
  async prepareRequest(e2, t2) {
    const o2 = await this.getAccessToken(t2);
    let n2, i2;
    "string" == typeof o2 ? (n2 = this.config.dpopNonceId ? Ne.DPoP : Ne.Bearer, i2 = o2) : (n2 = o2.token_type, i2 = o2.access_token), this.setAuthorizationHeader(e2, i2, n2), n2 === Ne.DPoP && await this.setDpopProofHeader(e2, i2);
  }
  getHeader(e2, t2) {
    return Array.isArray(e2) ? new Headers(e2).get(t2) || "" : "function" == typeof e2.get ? e2.get(t2) || "" : e2[t2] || "";
  }
  hasUseDpopNonceError(e2) {
    if (401 !== e2.status) return false;
    const t2 = this.getHeader(e2.headers, "www-authenticate");
    return t2.includes("invalid_dpop_nonce") || t2.includes("use_dpop_nonce");
  }
  async handleResponse(e2, t2) {
    const o2 = this.getHeader(e2.headers, "dpop-nonce");
    if (o2 && await this.hooks.setDpopNonce(o2), !this.hasUseDpopNonceError(e2)) return e2;
    if (!o2 || !t2.onUseDpopNonceError) throw new b(o2);
    return t2.onUseDpopNonceError();
  }
  async internalFetchWithAuth(e2, t2, o2, n2) {
    const i2 = this.buildBaseRequest(e2, t2);
    await this.prepareRequest(i2, n2);
    const r2 = await this.config.fetch(i2);
    return this.handleResponse(r2, o2);
  }
  fetchWithAuth(e2, t2, o2) {
    const n2 = { onUseDpopNonceError: () => this.internalFetchWithAuth(e2, t2, Object.assign(Object.assign({}, n2), { onUseDpopNonceError: void 0 }), o2) };
    return this.internalFetchWithAuth(e2, t2, n2, o2);
  }
}
class De {
  constructor(e2, t2) {
    this.myAccountFetcher = e2, this.apiBase = t2;
  }
  async connectAccount(e2) {
    const t2 = await this.myAccountFetcher.fetchWithAuth(`${this.apiBase}v1/connected-accounts/connect`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(e2) });
    return this._handleResponse(t2);
  }
  async completeAccount(e2) {
    const t2 = await this.myAccountFetcher.fetchWithAuth(`${this.apiBase}v1/connected-accounts/complete`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(e2) });
    return this._handleResponse(t2);
  }
  async _handleResponse(e2) {
    let t2;
    try {
      t2 = await e2.text(), t2 = JSON.parse(t2);
    } catch (o2) {
      throw new Ae({ type: "invalid_json", status: e2.status, title: "Invalid JSON response", detail: t2 || String(o2) });
    }
    if (e2.ok) return t2;
    throw new Ae(t2);
  }
}
class Ae extends Error {
  constructor({ type: e2, status: t2, title: o2, detail: n2, validation_errors: i2 }) {
    super(n2), this.name = "MyAccountApiError", this.type = e2, this.status = t2, this.title = o2, this.detail = n2, this.validation_errors = i2, Object.setPrototypeOf(this, Ae.prototype);
  }
}
const Ue = new r();
class Le {
  constructor(e2) {
    let t2, o2;
    if (this.userCache = new ie().enclosedCache, this.activeLockKeys = /* @__PURE__ */ new Set(), this.defaultOptions = { authorizationParams: { scope: "openid profile email" }, useRefreshTokensFallback: false, useFormData: true }, this._releaseLockOnPageHide = async () => {
      const e3 = Array.from(this.activeLockKeys);
      for (const t3 of e3) await Ue.releaseLock(t3);
      this.activeLockKeys.clear(), window.removeEventListener("pagehide", this._releaseLockOnPageHide);
    }, this.options = Object.assign(Object.assign(Object.assign({}, this.defaultOptions), e2), { authorizationParams: Object.assign(Object.assign({}, this.defaultOptions.authorizationParams), e2.authorizationParams) }), "undefined" != typeof window && (() => {
      if (!v()) throw new Error("For security reasons, `window.crypto` is required to run `auth0-spa-js`.");
      if (void 0 === v().subtle) throw new Error("\n      auth0-spa-js must run on a secure origin. See https://github.com/auth0/auth0-spa-js/blob/main/FAQ.md#why-do-i-get-auth0-spa-js-must-run-on-a-secure-origin for more information.\n    ");
    })(), e2.cache && e2.cacheLocation && console.warn("Both `cache` and `cacheLocation` options have been specified in the Auth0Client configuration; ignoring `cacheLocation` and using `cache`."), e2.cache) o2 = e2.cache;
    else {
      if (t2 = e2.cacheLocation || "memory", !je(t2)) throw new Error(`Invalid cache location "${t2}"`);
      o2 = je(t2)();
    }
    this.httpTimeoutMs = e2.httpTimeoutInSeconds ? 1e3 * e2.httpTimeoutInSeconds : 1e4, this.cookieStorage = false === e2.legacySameSiteCookie ? me : fe, this.orgHintCookieName = `auth0.${this.options.clientId}.organization_hint`, this.isAuthenticatedCookieName = ((e3) => `auth0.${e3}.is.authenticated`)(this.options.clientId), this.sessionCheckExpiryDays = e2.sessionCheckExpiryDays || 1;
    const n2 = e2.useCookiesForTransactions ? this.cookieStorage : ge;
    var i2;
    this.scope = ((e3, t3, ...o3) => {
      if ("object" != typeof e3) return { default: ee(t3, e3, ...o3) };
      let n3 = { default: ee(t3, ...o3) };
      return Object.keys(e3).forEach(((i3) => {
        const r3 = e3[i3];
        n3[i3] = ee(t3, r3, ...o3);
      })), n3;
    })(this.options.authorizationParams.scope, "openid", this.options.useRefreshTokens ? "offline_access" : ""), this.transactionManager = new se(n2, this.options.clientId, this.options.cookieDomain), this.nowProvider = this.options.nowProvider || c, this.cacheManager = new re(o2, o2.allKeys ? void 0 : new Te(o2, this.options.clientId), this.nowProvider), this.dpop = this.options.useDpop ? new Ee(this.options.clientId) : void 0, this.domainUrl = (i2 = this.options.domain, /^https?:\/\//.test(i2) ? i2 : `https://${i2}`), this.tokenIssuer = ((e3, t3) => e3 ? e3.startsWith("https://") ? e3 : `https://${e3}/` : `${t3}/`)(this.options.issuer, this.domainUrl);
    const r2 = `${this.domainUrl}/me/`, s2 = this.createFetcher(Object.assign(Object.assign({}, this.options.useDpop && { dpopNonceId: "__auth0_my_account_api__" }), { getAccessToken: () => this.getTokenSilently({ authorizationParams: { scope: "create:me:connected_accounts", audience: r2 }, detailedResponse: true }) }));
    this.myAccountApi = new De(s2, r2), "undefined" != typeof window && window.Worker && this.options.useRefreshTokens && "memory" === t2 && (this.options.workerUrl ? this.worker = new Worker(this.options.workerUrl) : this.worker = new Ie());
  }
  _url(e2) {
    const t2 = encodeURIComponent(btoa(JSON.stringify(this.options.auth0Client || a)));
    return `${this.domainUrl}${e2}&auth0Client=${t2}`;
  }
  _authorizeUrl(e2) {
    return this._url(`/authorize?${T(e2)}`);
  }
  async _verifyIdToken(e2, t2, o2) {
    const n2 = await this.nowProvider();
    return ue({ iss: this.tokenIssuer, aud: this.options.clientId, id_token: e2, nonce: t2, organization: o2, leeway: this.options.leeway, max_age: (i2 = this.options.authorizationParams.max_age, "string" != typeof i2 ? i2 : parseInt(i2, 10) || void 0), now: n2 });
    var i2;
  }
  _processOrgHint(e2) {
    e2 ? this.cookieStorage.save(this.orgHintCookieName, e2, { daysUntilExpire: this.sessionCheckExpiryDays, cookieDomain: this.options.cookieDomain }) : this.cookieStorage.remove(this.orgHintCookieName, { cookieDomain: this.options.cookieDomain });
  }
  async _prepareAuthorizeUrl(e2, t2, o2) {
    var n2;
    const i2 = S(_()), r2 = S(_()), s2 = _(), a2 = await O(s2), c2 = C(a2), u2 = await (null === (n2 = this.dpop) || void 0 === n2 ? void 0 : n2.calculateThumbprint()), d2 = ((e3, t3, o3, n3, i3, r3, s3, a3, c3) => Object.assign(Object.assign(Object.assign({ client_id: e3.clientId }, e3.authorizationParams), o3), { scope: te(t3, o3.scope, o3.audience), response_type: "code", response_mode: a3 || "query", state: n3, nonce: i3, redirect_uri: s3 || e3.authorizationParams.redirect_uri, code_challenge: r3, code_challenge_method: "S256", dpop_jkt: c3 }))(this.options, this.scope, e2, i2, r2, c2, e2.redirect_uri || this.options.authorizationParams.redirect_uri || o2, null == t2 ? void 0 : t2.response_mode, u2), h2 = this._authorizeUrl(d2);
    return { nonce: r2, code_verifier: s2, scope: d2.scope, audience: d2.audience || "default", redirect_uri: d2.redirect_uri, state: i2, url: h2 };
  }
  async loginWithPopup(e2, t2) {
    var o2;
    if (e2 = e2 || {}, !(t2 = t2 || {}).popup && (t2.popup = ((e3) => {
      const t3 = window.screenX + (window.innerWidth - 400) / 2, o3 = window.screenY + (window.innerHeight - 600) / 2;
      return window.open(e3, "auth0:authorize:popup", `left=${t3},top=${o3},width=400,height=600,resizable,scrollbars=yes,status=1`);
    })(""), !t2.popup)) throw new f();
    const n2 = await this._prepareAuthorizeUrl(e2.authorizationParams || {}, { response_mode: "web_message" }, window.location.origin);
    t2.popup.location.href = n2.url;
    const i2 = await ((e3) => new Promise(((t3, o3) => {
      let n3;
      const i3 = setInterval((() => {
        e3.popup && e3.popup.closed && (clearInterval(i3), clearTimeout(r3), window.removeEventListener("message", n3, false), o3(new m(e3.popup)));
      }), 1e3), r3 = setTimeout((() => {
        clearInterval(i3), o3(new p(e3.popup)), window.removeEventListener("message", n3, false);
      }), 1e3 * (e3.timeoutInSeconds || 60));
      n3 = function(s2) {
        if (s2.data && "authorization_response" === s2.data.type) {
          if (clearTimeout(r3), clearInterval(i3), window.removeEventListener("message", n3, false), e3.popup.close(), s2.data.response.error) return o3(u.fromPayload(s2.data.response));
          t3(s2.data.response);
        }
      }, window.addEventListener("message", n3);
    })))(Object.assign(Object.assign({}, t2), { timeoutInSeconds: t2.timeoutInSeconds || this.options.authorizeTimeoutInSeconds || 60 }));
    if (n2.state !== i2.state) throw new u("state_mismatch", "Invalid state");
    const r2 = (null === (o2 = e2.authorizationParams) || void 0 === o2 ? void 0 : o2.organization) || this.options.authorizationParams.organization;
    await this._requestToken({ audience: n2.audience, scope: n2.scope, code_verifier: n2.code_verifier, grant_type: "authorization_code", code: i2.code, redirect_uri: n2.redirect_uri }, { nonceIn: n2.nonce, organization: r2 });
  }
  async getUser() {
    var e2;
    const t2 = await this._getIdTokenFromCache();
    return null === (e2 = null == t2 ? void 0 : t2.decodedToken) || void 0 === e2 ? void 0 : e2.user;
  }
  async getIdTokenClaims() {
    var e2;
    const t2 = await this._getIdTokenFromCache();
    return null === (e2 = null == t2 ? void 0 : t2.decodedToken) || void 0 === e2 ? void 0 : e2.claims;
  }
  async loginWithRedirect(t2 = {}) {
    var o2;
    const n2 = Ce(t2), { openUrl: i2, fragment: r2, appState: s2 } = n2, a2 = e(n2, ["openUrl", "fragment", "appState"]), c2 = (null === (o2 = a2.authorizationParams) || void 0 === o2 ? void 0 : o2.organization) || this.options.authorizationParams.organization, u2 = await this._prepareAuthorizeUrl(a2.authorizationParams || {}), { url: d2 } = u2, h2 = e(u2, ["url"]);
    this.transactionManager.create(Object.assign(Object.assign(Object.assign({}, h2), { appState: s2, response_type: ye.Code }), c2 && { organization: c2 }));
    const l2 = r2 ? `${d2}#${r2}` : d2;
    i2 ? await i2(l2) : window.location.assign(l2);
  }
  async handleRedirectCallback(e2 = window.location.href) {
    const t2 = e2.split("?").slice(1);
    if (0 === t2.length) throw new Error("There are no query params available for parsing.");
    const o2 = this.transactionManager.get();
    if (!o2) throw new u("missing_transaction", "Invalid state");
    this.transactionManager.remove();
    const n2 = ((e3) => {
      e3.indexOf("#") > -1 && (e3 = e3.substring(0, e3.indexOf("#")));
      const t3 = new URLSearchParams(e3);
      return { state: t3.get("state"), code: t3.get("code") || void 0, connect_code: t3.get("connect_code") || void 0, error: t3.get("error") || void 0, error_description: t3.get("error_description") || void 0 };
    })(t2.join(""));
    return o2.response_type === ye.ConnectCode ? this._handleConnectAccountRedirectCallback(n2, o2) : this._handleLoginRedirectCallback(n2, o2);
  }
  async _handleLoginRedirectCallback(e2, t2) {
    const { code: o2, state: n2, error: i2, error_description: r2 } = e2;
    if (i2) throw new d(i2, r2 || i2, n2, t2.appState);
    if (!t2.code_verifier || t2.state && t2.state !== n2) throw new u("state_mismatch", "Invalid state");
    const s2 = t2.organization, a2 = t2.nonce, c2 = t2.redirect_uri;
    return await this._requestToken(Object.assign({ audience: t2.audience, scope: t2.scope, code_verifier: t2.code_verifier, grant_type: "authorization_code", code: o2 }, c2 ? { redirect_uri: c2 } : {}), { nonceIn: a2, organization: s2 }), { appState: t2.appState, response_type: ye.Code };
  }
  async _handleConnectAccountRedirectCallback(e2, t2) {
    const { connect_code: o2, state: n2, error: i2, error_description: r2 } = e2;
    if (i2) throw new h(i2, r2 || i2, t2.connection, n2, t2.appState);
    if (!o2) throw new u("missing_connect_code", "Missing connect code");
    if (!(t2.code_verifier && t2.state && t2.auth_session && t2.redirect_uri && t2.state === n2)) throw new u("state_mismatch", "Invalid state");
    const s2 = await this.myAccountApi.completeAccount({ auth_session: t2.auth_session, connect_code: o2, redirect_uri: t2.redirect_uri, code_verifier: t2.code_verifier });
    return Object.assign(Object.assign({}, s2), { appState: t2.appState, response_type: ye.ConnectCode });
  }
  async checkSession(e2) {
    if (!this.cookieStorage.get(this.isAuthenticatedCookieName)) {
      if (!this.cookieStorage.get("auth0.is.authenticated")) return;
      this.cookieStorage.save(this.isAuthenticatedCookieName, true, { daysUntilExpire: this.sessionCheckExpiryDays, cookieDomain: this.options.cookieDomain }), this.cookieStorage.remove("auth0.is.authenticated");
    }
    try {
      await this.getTokenSilently(e2);
    } catch (e3) {
    }
  }
  async getTokenSilently(e2 = {}) {
    var t2, o2;
    const n2 = Object.assign(Object.assign({ cacheMode: "on" }, e2), { authorizationParams: Object.assign(Object.assign(Object.assign({}, this.options.authorizationParams), e2.authorizationParams), { scope: te(this.scope, null === (t2 = e2.authorizationParams) || void 0 === t2 ? void 0 : t2.scope, (null === (o2 = e2.authorizationParams) || void 0 === o2 ? void 0 : o2.audience) || this.options.authorizationParams.audience) }) }), i2 = await ((e3, t3) => {
      let o3 = Pe[t3];
      return o3 || (o3 = e3().finally((() => {
        delete Pe[t3], o3 = null;
      })), Pe[t3] = o3), o3;
    })((() => this._getTokenSilently(n2)), `${this.options.clientId}::${n2.authorizationParams.audience}::${n2.authorizationParams.scope}`);
    return e2.detailedResponse ? i2 : null == i2 ? void 0 : i2.access_token;
  }
  async _getTokenSilently(t2) {
    const { cacheMode: o2 } = t2, n2 = e(t2, ["cacheMode"]);
    if ("off" !== o2) {
      const e2 = await this._getEntryFromCache({ scope: n2.authorizationParams.scope, audience: n2.authorizationParams.audience || "default", clientId: this.options.clientId, cacheMode: o2 });
      if (e2) return e2;
    }
    if ("cache-only" === o2) return;
    const i2 = (r2 = this.options.clientId, s2 = n2.authorizationParams.audience || "default", `auth0.lock.getTokenSilently.${r2}.${s2}`);
    var r2, s2;
    if (!await (async (e2, t3 = 3) => {
      for (let o3 = 0; o3 < t3; o3++) if (await e2()) return true;
      return false;
    })((() => Ue.acquireLock(i2, 5e3)), 10)) throw new l();
    this.activeLockKeys.add(i2), 1 === this.activeLockKeys.size && window.addEventListener("pagehide", this._releaseLockOnPageHide);
    try {
      if ("off" !== o2) {
        const e3 = await this._getEntryFromCache({ scope: n2.authorizationParams.scope, audience: n2.authorizationParams.audience || "default", clientId: this.options.clientId });
        if (e3) return e3;
      }
      const e2 = this.options.useRefreshTokens ? await this._getTokenUsingRefreshToken(n2) : await this._getTokenFromIFrame(n2), { id_token: t3, token_type: r3, access_token: s3, oauthTokenScope: a2, expires_in: c2 } = e2;
      return Object.assign(Object.assign({ id_token: t3, token_type: r3, access_token: s3 }, a2 ? { scope: a2 } : null), { expires_in: c2 });
    } finally {
      await Ue.releaseLock(i2), this.activeLockKeys.delete(i2), 0 === this.activeLockKeys.size && window.removeEventListener("pagehide", this._releaseLockOnPageHide);
    }
  }
  async getTokenWithPopup(e2 = {}, t2 = {}) {
    var o2, n2;
    const i2 = Object.assign(Object.assign({}, e2), { authorizationParams: Object.assign(Object.assign(Object.assign({}, this.options.authorizationParams), e2.authorizationParams), { scope: te(this.scope, null === (o2 = e2.authorizationParams) || void 0 === o2 ? void 0 : o2.scope, (null === (n2 = e2.authorizationParams) || void 0 === n2 ? void 0 : n2.audience) || this.options.authorizationParams.audience) }) });
    t2 = Object.assign(Object.assign({}, s), t2), await this.loginWithPopup(i2, t2);
    return (await this.cacheManager.get(new oe({ scope: i2.authorizationParams.scope, audience: i2.authorizationParams.audience || "default", clientId: this.options.clientId }), void 0, this.options.useMrrt)).access_token;
  }
  async isAuthenticated() {
    return !!await this.getUser();
  }
  _buildLogoutUrl(t2) {
    null !== t2.clientId ? t2.clientId = t2.clientId || this.options.clientId : delete t2.clientId;
    const o2 = t2.logoutParams || {}, { federated: n2 } = o2, i2 = e(o2, ["federated"]), r2 = n2 ? "&federated" : "";
    return this._url(`/v2/logout?${T(Object.assign({ clientId: t2.clientId }, i2))}`) + r2;
  }
  async logout(t2 = {}) {
    var o2;
    const n2 = Ce(t2), { openUrl: i2 } = n2, r2 = e(n2, ["openUrl"]);
    null === t2.clientId ? await this.cacheManager.clear() : await this.cacheManager.clear(t2.clientId || this.options.clientId), this.cookieStorage.remove(this.orgHintCookieName, { cookieDomain: this.options.cookieDomain }), this.cookieStorage.remove(this.isAuthenticatedCookieName, { cookieDomain: this.options.cookieDomain }), this.userCache.remove("@@user@@"), await (null === (o2 = this.dpop) || void 0 === o2 ? void 0 : o2.clear());
    const s2 = this._buildLogoutUrl(r2);
    i2 ? await i2(s2) : false !== i2 && window.location.assign(s2);
  }
  async _getTokenFromIFrame(e2) {
    const t2 = Object.assign(Object.assign({}, e2.authorizationParams), { prompt: "none" }), o2 = this.cookieStorage.get(this.orgHintCookieName);
    o2 && !t2.organization && (t2.organization = o2);
    const { url: n2, state: i2, nonce: r2, code_verifier: s2, redirect_uri: a2, scope: c2, audience: d2 } = await this._prepareAuthorizeUrl(t2, { response_mode: "web_message" }, window.location.origin);
    try {
      if (window.crossOriginIsolated) throw new u("login_required", "The application is running in a Cross-Origin Isolated context, silently retrieving a token without refresh token is not possible.");
      const o3 = e2.timeoutInSeconds || this.options.authorizeTimeoutInSeconds;
      let h2;
      try {
        h2 = new URL(this.domainUrl).origin;
      } catch (e3) {
        h2 = this.domainUrl;
      }
      const p2 = await ((e3, t3, o4 = 60) => new Promise(((n3, i3) => {
        const r3 = window.document.createElement("iframe");
        r3.setAttribute("width", "0"), r3.setAttribute("height", "0"), r3.style.display = "none";
        const s3 = () => {
          window.document.body.contains(r3) && (window.document.body.removeChild(r3), window.removeEventListener("message", a3, false));
        };
        let a3;
        const c3 = setTimeout((() => {
          i3(new l()), s3();
        }), 1e3 * o4);
        a3 = function(e4) {
          if (e4.origin != t3) return;
          if (!e4.data || "authorization_response" !== e4.data.type) return;
          const o5 = e4.source;
          o5 && o5.close(), e4.data.response.error ? i3(u.fromPayload(e4.data.response)) : n3(e4.data.response), clearTimeout(c3), window.removeEventListener("message", a3, false), setTimeout(s3, 2e3);
        }, window.addEventListener("message", a3, false), window.document.body.appendChild(r3), r3.setAttribute("src", e3);
      })))(n2, h2, o3);
      if (i2 !== p2.state) throw new u("state_mismatch", "Invalid state");
      const m2 = await this._requestToken(Object.assign(Object.assign({}, e2.authorizationParams), { code_verifier: s2, code: p2.code, grant_type: "authorization_code", redirect_uri: a2, timeout: e2.authorizationParams.timeout || this.httpTimeoutMs }), { nonceIn: r2, organization: t2.organization });
      return Object.assign(Object.assign({}, m2), { scope: c2, oauthTokenScope: m2.scope, audience: d2 });
    } catch (e3) {
      throw "login_required" === e3.error && this.logout({ openUrl: false }), e3;
    }
  }
  async _getTokenUsingRefreshToken(e2) {
    const t2 = await this.cacheManager.get(new oe({ scope: e2.authorizationParams.scope, audience: e2.authorizationParams.audience || "default", clientId: this.options.clientId }), void 0, this.options.useMrrt);
    if (!(t2 && t2.refresh_token || this.worker)) {
      if (this.options.useRefreshTokensFallback) return await this._getTokenFromIFrame(e2);
      throw new y(e2.authorizationParams.audience || "default", e2.authorizationParams.scope);
    }
    const o2 = e2.authorizationParams.redirect_uri || this.options.authorizationParams.redirect_uri || window.location.origin, n2 = "number" == typeof e2.timeoutInSeconds ? 1e3 * e2.timeoutInSeconds : null, i2 = ((e3, t3, o3, n3) => {
      var i3;
      if (e3 && o3 && n3) {
        if (t3.audience !== o3) return t3.scope;
        const e4 = n3.split(" "), r3 = (null === (i3 = t3.scope) || void 0 === i3 ? void 0 : i3.split(" ")) || [], s3 = r3.every(((t4) => e4.includes(t4)));
        return e4.length >= r3.length && s3 ? n3 : t3.scope;
      }
      return t3.scope;
    })(this.options.useMrrt, e2.authorizationParams, null == t2 ? void 0 : t2.audience, null == t2 ? void 0 : t2.scope);
    try {
      const u2 = await this._requestToken(Object.assign(Object.assign(Object.assign({}, e2.authorizationParams), { grant_type: "refresh_token", refresh_token: t2 && t2.refresh_token, redirect_uri: o2 }), n2 && { timeout: n2 }), { scopesToRequest: i2 });
      if (u2.refresh_token && this.options.useMrrt && (null == t2 ? void 0 : t2.refresh_token) && await this.cacheManager.updateEntry(t2.refresh_token, u2.refresh_token), this.options.useMrrt) {
        if (r2 = null == t2 ? void 0 : t2.audience, s2 = null == t2 ? void 0 : t2.scope, a2 = e2.authorizationParams.audience, c2 = e2.authorizationParams.scope, r2 !== a2 || !Ke(c2, s2)) {
          if (!Ke(i2, u2.scope)) {
            if (this.options.useRefreshTokensFallback) return await this._getTokenFromIFrame(e2);
            await this.cacheManager.remove(this.options.clientId, e2.authorizationParams.audience, e2.authorizationParams.scope);
            const t3 = ((e3, t4) => {
              const o3 = (null == e3 ? void 0 : e3.split(" ")) || [], n3 = (null == t4 ? void 0 : t4.split(" ")) || [];
              return o3.filter(((e4) => -1 == n3.indexOf(e4))).join(",");
            })(i2, u2.scope);
            throw new w(e2.authorizationParams.audience || "default", t3);
          }
        }
      }
      return Object.assign(Object.assign({}, u2), { scope: e2.authorizationParams.scope, oauthTokenScope: u2.scope, audience: e2.authorizationParams.audience || "default" });
    } catch (t3) {
      if ((t3.message.indexOf("Missing Refresh Token") > -1 || t3.message && t3.message.indexOf("invalid refresh token") > -1) && this.options.useRefreshTokensFallback) return await this._getTokenFromIFrame(e2);
      throw t3;
    }
    var r2, s2, a2, c2;
  }
  async _saveEntryInCache(t2) {
    const { id_token: o2, decodedToken: n2 } = t2, i2 = e(t2, ["id_token", "decodedToken"]);
    this.userCache.set("@@user@@", { id_token: o2, decodedToken: n2 }), await this.cacheManager.setIdToken(this.options.clientId, t2.id_token, t2.decodedToken), await this.cacheManager.set(i2);
  }
  async _getIdTokenFromCache() {
    const e2 = this.options.authorizationParams.audience || "default", t2 = this.scope[e2], o2 = await this.cacheManager.getIdToken(new oe({ clientId: this.options.clientId, audience: e2, scope: t2 })), n2 = this.userCache.get("@@user@@");
    return o2 && o2.id_token === (null == n2 ? void 0 : n2.id_token) ? n2 : (this.userCache.set("@@user@@", o2), o2);
  }
  async _getEntryFromCache({ scope: e2, audience: t2, clientId: o2, cacheMode: n2 }) {
    const i2 = await this.cacheManager.get(new oe({ scope: e2, audience: t2, clientId: o2 }), 60, this.options.useMrrt, n2);
    if (i2 && i2.access_token) {
      const { token_type: e3, access_token: t3, oauthTokenScope: o3, expires_in: n3 } = i2, r2 = await this._getIdTokenFromCache();
      return r2 && Object.assign(Object.assign({ id_token: r2.id_token, token_type: e3 || "Bearer", access_token: t3 }, o3 ? { scope: o3 } : null), { expires_in: n3 });
    }
  }
  async _requestToken(e2, t2) {
    const { nonceIn: o2, organization: n2, scopesToRequest: i2 } = t2 || {}, r2 = await Q(Object.assign(Object.assign({ baseUrl: this.domainUrl, client_id: this.options.clientId, auth0Client: this.options.auth0Client, useFormData: this.options.useFormData, timeout: this.httpTimeoutMs, useMrrt: this.options.useMrrt, dpop: this.dpop }, e2), { scope: i2 || e2.scope }), this.worker), s2 = await this._verifyIdToken(r2.id_token, o2, n2);
    return await this._saveEntryInCache(Object.assign(Object.assign(Object.assign(Object.assign({}, r2), { decodedToken: s2, scope: e2.scope, audience: e2.audience || "default" }), r2.scope ? { oauthTokenScope: r2.scope } : null), { client_id: this.options.clientId })), this.cookieStorage.save(this.isAuthenticatedCookieName, true, { daysUntilExpire: this.sessionCheckExpiryDays, cookieDomain: this.options.cookieDomain }), this._processOrgHint(n2 || s2.claims.org_id), Object.assign(Object.assign({}, r2), { decodedToken: s2 });
  }
  async exchangeToken(e2) {
    return this._requestToken({ grant_type: "urn:ietf:params:oauth:grant-type:token-exchange", subject_token: e2.subject_token, subject_token_type: e2.subject_token_type, scope: te(this.scope, e2.scope, e2.audience || this.options.authorizationParams.audience), audience: e2.audience || this.options.authorizationParams.audience, organization: e2.organization || this.options.authorizationParams.organization });
  }
  _assertDpop(e2) {
    if (!e2) throw new Error("`useDpop` option must be enabled before using DPoP.");
  }
  getDpopNonce(e2) {
    return this._assertDpop(this.dpop), this.dpop.getNonce(e2);
  }
  setDpopNonce(e2, t2) {
    return this._assertDpop(this.dpop), this.dpop.setNonce(e2, t2);
  }
  generateDpopProof(e2) {
    return this._assertDpop(this.dpop), this.dpop.generateProof(e2);
  }
  createFetcher(e2 = {}) {
    return new Re(e2, { isDpopEnabled: () => !!this.options.useDpop, getAccessToken: (e3) => {
      var t2;
      return this.getTokenSilently({ authorizationParams: { scope: null === (t2 = null == e3 ? void 0 : e3.scope) || void 0 === t2 ? void 0 : t2.join(" "), audience: null == e3 ? void 0 : e3.audience }, detailedResponse: true });
    }, getDpopNonce: () => this.getDpopNonce(e2.dpopNonceId), setDpopNonce: (t2) => this.setDpopNonce(t2, e2.dpopNonceId), generateDpopProof: (e3) => this.generateDpopProof(e3) });
  }
  async connectAccountWithRedirect(e2) {
    const { openUrl: t2, appState: o2, connection: n2, scopes: i2, authorization_params: r2, redirectUri: s2 = this.options.authorizationParams.redirect_uri || window.location.origin } = e2;
    if (!n2) throw new Error("connection is required");
    const a2 = S(_()), c2 = _(), u2 = await O(c2), d2 = C(u2), { connect_uri: h2, connect_params: l2, auth_session: p2 } = await this.myAccountApi.connectAccount({ connection: n2, scopes: i2, redirect_uri: s2, state: a2, code_challenge: d2, code_challenge_method: "S256", authorization_params: r2 });
    this.transactionManager.create({ state: a2, code_verifier: c2, auth_session: p2, redirect_uri: s2, appState: o2, connection: n2, response_type: ye.ConnectCode });
    const m2 = new URL(h2);
    m2.searchParams.set("ticket", l2.ticket), t2 ? await t2(m2.toString()) : window.location.assign(m2);
  }
}
var initialAuthState = {
  isAuthenticated: false,
  isLoading: true,
  error: void 0,
  user: void 0
};
var stub = function() {
  throw new Error("You forgot to wrap your component in <Auth0Provider>.");
};
var initialContext = __assign(__assign({}, initialAuthState), { buildAuthorizeUrl: stub, buildLogoutUrl: stub, getAccessTokenSilently: stub, getAccessTokenWithPopup: stub, getIdTokenClaims: stub, exchangeToken: stub, loginWithRedirect: stub, loginWithPopup: stub, connectAccountWithRedirect: stub, logout: stub, handleRedirectCallback: stub, getDpopNonce: stub, setDpopNonce: stub, generateDpopProof: stub, createFetcher: stub });
var Auth0Context = createContext(initialContext);
var OAuthError = (
  /** @class */
  (function(_super) {
    __extends(OAuthError2, _super);
    function OAuthError2(error, error_description) {
      var _this = _super.call(this, error_description !== null && error_description !== void 0 ? error_description : error) || this;
      _this.error = error;
      _this.error_description = error_description;
      Object.setPrototypeOf(_this, OAuthError2.prototype);
      return _this;
    }
    return OAuthError2;
  })(Error)
);
var CODE_RE = /[?&](?:connect_)?code=[^&]+/;
var STATE_RE = /[?&]state=[^&]+/;
var ERROR_RE = /[?&]error=[^&]+/;
var hasAuthParams = function(searchParams) {
  if (searchParams === void 0) {
    searchParams = window.location.search;
  }
  return (CODE_RE.test(searchParams) || ERROR_RE.test(searchParams)) && STATE_RE.test(searchParams);
};
var normalizeErrorFn = function(fallbackMessage) {
  return function(error) {
    if (error instanceof Error) {
      return error;
    }
    if (error !== null && typeof error === "object" && "error" in error && typeof error.error === "string") {
      if ("error_description" in error && typeof error.error_description === "string") {
        var e_1 = error;
        return new OAuthError(e_1.error, e_1.error_description);
      }
      var e2 = error;
      return new OAuthError(e2.error);
    }
    return new Error(fallbackMessage);
  };
};
var loginError = normalizeErrorFn("Login failed");
var tokenError = normalizeErrorFn("Get access token failed");
var deprecateRedirectUri = function(options) {
  var _a, _b;
  if (options === null || options === void 0 ? void 0 : options.redirectUri) {
    console.warn("Using `redirectUri` has been deprecated, please use `authorizationParams.redirect_uri` instead as `redirectUri` will be no longer supported in a future version");
    options.authorizationParams = (_a = options.authorizationParams) !== null && _a !== void 0 ? _a : {};
    options.authorizationParams.redirect_uri = options.redirectUri;
    delete options.redirectUri;
  }
  if ((_b = options === null || options === void 0 ? void 0 : options.authorizationParams) === null || _b === void 0 ? void 0 : _b.redirectUri) {
    console.warn("Using `authorizationParams.redirectUri` has been deprecated, please use `authorizationParams.redirect_uri` instead as `authorizationParams.redirectUri` will be removed in a future version");
    options.authorizationParams.redirect_uri = options.authorizationParams.redirectUri;
    delete options.authorizationParams.redirectUri;
  }
};
var reducer = function(state, action) {
  switch (action.type) {
    case "LOGIN_POPUP_STARTED":
      return __assign(__assign({}, state), { isLoading: true });
    case "LOGIN_POPUP_COMPLETE":
    case "INITIALISED":
      return __assign(__assign({}, state), { isAuthenticated: !!action.user, user: action.user, isLoading: false, error: void 0 });
    case "HANDLE_REDIRECT_COMPLETE":
    case "GET_ACCESS_TOKEN_COMPLETE":
      if (state.user === action.user) {
        return state;
      }
      return __assign(__assign({}, state), { isAuthenticated: !!action.user, user: action.user });
    case "LOGOUT":
      return __assign(__assign({}, state), { isAuthenticated: false, user: void 0 });
    case "ERROR":
      return __assign(__assign({}, state), { isLoading: false, error: action.error });
  }
};
var toAuth0ClientOptions = function(opts) {
  deprecateRedirectUri(opts);
  return __assign(__assign({}, opts), { auth0Client: {
    name: "auth0-react",
    version: "2.11.0"
  } });
};
var defaultOnRedirectCallback = function(appState) {
  var _a;
  window.history.replaceState({}, document.title, (_a = appState.returnTo) !== null && _a !== void 0 ? _a : window.location.pathname);
};
var Auth0Provider = function(opts) {
  var children = opts.children, skipRedirectCallback = opts.skipRedirectCallback, _a = opts.onRedirectCallback, onRedirectCallback = _a === void 0 ? defaultOnRedirectCallback : _a, _b = opts.context, context = _b === void 0 ? Auth0Context : _b, clientOpts = __rest(opts, ["children", "skipRedirectCallback", "onRedirectCallback", "context"]);
  var client = useState(function() {
    return new Le(toAuth0ClientOptions(clientOpts));
  })[0];
  var _c = useReducer(reducer, initialAuthState), state = _c[0], dispatch = _c[1];
  var didInitialise = useRef(false);
  var handleError = useCallback(function(error) {
    dispatch({ type: "ERROR", error });
    return error;
  }, []);
  useEffect(function() {
    if (didInitialise.current) {
      return;
    }
    didInitialise.current = true;
    (function() {
      return __awaiter(void 0, void 0, void 0, function() {
        var user, _a2, _b2, appState, response_type, result, error_1;
        return __generator(this, function(_c2) {
          switch (_c2.label) {
            case 0:
              _c2.trys.push([0, 7, , 8]);
              user = void 0;
              if (!(hasAuthParams() && !skipRedirectCallback)) return [3, 3];
              return [4, client.handleRedirectCallback()];
            case 1:
              _a2 = _c2.sent(), _b2 = _a2.appState, appState = _b2 === void 0 ? {} : _b2, response_type = _a2.response_type, result = __rest(_a2, ["appState", "response_type"]);
              return [4, client.getUser()];
            case 2:
              user = _c2.sent();
              appState.response_type = response_type;
              if (response_type === ye.ConnectCode) {
                appState.connectedAccount = result;
              }
              onRedirectCallback(appState, user);
              return [3, 6];
            case 3:
              return [4, client.checkSession()];
            case 4:
              _c2.sent();
              return [4, client.getUser()];
            case 5:
              user = _c2.sent();
              _c2.label = 6;
            case 6:
              dispatch({ type: "INITIALISED", user });
              return [3, 8];
            case 7:
              error_1 = _c2.sent();
              handleError(loginError(error_1));
              return [3, 8];
            case 8:
              return [
                2
                /*return*/
              ];
          }
        });
      });
    })();
  }, [client, onRedirectCallback, skipRedirectCallback, handleError]);
  var loginWithRedirect = useCallback(function(opts2) {
    deprecateRedirectUri(opts2);
    return client.loginWithRedirect(opts2);
  }, [client]);
  var loginWithPopup = useCallback(function(options, config) {
    return __awaiter(void 0, void 0, void 0, function() {
      var error_2, user;
      return __generator(this, function(_a2) {
        switch (_a2.label) {
          case 0:
            dispatch({ type: "LOGIN_POPUP_STARTED" });
            _a2.label = 1;
          case 1:
            _a2.trys.push([1, 3, , 4]);
            return [4, client.loginWithPopup(options, config)];
          case 2:
            _a2.sent();
            return [3, 4];
          case 3:
            error_2 = _a2.sent();
            handleError(loginError(error_2));
            return [
              2
              /*return*/
            ];
          case 4:
            return [4, client.getUser()];
          case 5:
            user = _a2.sent();
            dispatch({ type: "LOGIN_POPUP_COMPLETE", user });
            return [
              2
              /*return*/
            ];
        }
      });
    });
  }, [client, handleError]);
  var logout = useCallback(function() {
    var args_1 = [];
    for (var _i = 0; _i < arguments.length; _i++) {
      args_1[_i] = arguments[_i];
    }
    return __awaiter(void 0, __spreadArray([], args_1), void 0, function(opts2) {
      if (opts2 === void 0) {
        opts2 = {};
      }
      return __generator(this, function(_a2) {
        switch (_a2.label) {
          case 0:
            return [4, client.logout(opts2)];
          case 1:
            _a2.sent();
            if (opts2.openUrl || opts2.openUrl === false) {
              dispatch({ type: "LOGOUT" });
            }
            return [
              2
              /*return*/
            ];
        }
      });
    });
  }, [client]);
  var getAccessTokenSilently = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    function(opts2) {
      return __awaiter(void 0, void 0, void 0, function() {
        var token, error_3, _a2;
        var _b2;
        return __generator(this, function(_c2) {
          switch (_c2.label) {
            case 0:
              _c2.trys.push([0, 2, 3, 5]);
              return [4, client.getTokenSilently(opts2)];
            case 1:
              token = _c2.sent();
              return [3, 5];
            case 2:
              error_3 = _c2.sent();
              throw tokenError(error_3);
            case 3:
              _a2 = dispatch;
              _b2 = {
                type: "GET_ACCESS_TOKEN_COMPLETE"
              };
              return [4, client.getUser()];
            case 4:
              _a2.apply(void 0, [(_b2.user = _c2.sent(), _b2)]);
              return [
                7
                /*endfinally*/
              ];
            case 5:
              return [2, token];
          }
        });
      });
    },
    [client]
  );
  var getAccessTokenWithPopup = useCallback(function(opts2, config) {
    return __awaiter(void 0, void 0, void 0, function() {
      var token, error_4, _a2;
      var _b2;
      return __generator(this, function(_c2) {
        switch (_c2.label) {
          case 0:
            _c2.trys.push([0, 2, 3, 5]);
            return [4, client.getTokenWithPopup(opts2, config)];
          case 1:
            token = _c2.sent();
            return [3, 5];
          case 2:
            error_4 = _c2.sent();
            throw tokenError(error_4);
          case 3:
            _a2 = dispatch;
            _b2 = {
              type: "GET_ACCESS_TOKEN_COMPLETE"
            };
            return [4, client.getUser()];
          case 4:
            _a2.apply(void 0, [(_b2.user = _c2.sent(), _b2)]);
            return [
              7
              /*endfinally*/
            ];
          case 5:
            return [2, token];
        }
      });
    });
  }, [client]);
  var connectAccountWithRedirect = useCallback(function(options) {
    return client.connectAccountWithRedirect(options);
  }, [client]);
  var getIdTokenClaims = useCallback(function() {
    return client.getIdTokenClaims();
  }, [client]);
  var exchangeToken = useCallback(function(options) {
    return __awaiter(void 0, void 0, void 0, function() {
      var tokenResponse, error_5, _a2;
      var _b2;
      return __generator(this, function(_c2) {
        switch (_c2.label) {
          case 0:
            _c2.trys.push([0, 2, 3, 5]);
            return [4, client.exchangeToken(options)];
          case 1:
            tokenResponse = _c2.sent();
            return [3, 5];
          case 2:
            error_5 = _c2.sent();
            throw tokenError(error_5);
          case 3:
            _a2 = dispatch;
            _b2 = {
              type: "GET_ACCESS_TOKEN_COMPLETE"
            };
            return [4, client.getUser()];
          case 4:
            _a2.apply(void 0, [(_b2.user = _c2.sent(), _b2)]);
            return [
              7
              /*endfinally*/
            ];
          case 5:
            return [2, tokenResponse];
        }
      });
    });
  }, [client]);
  var handleRedirectCallback = useCallback(function(url) {
    return __awaiter(void 0, void 0, void 0, function() {
      var error_6, _a2;
      var _b2;
      return __generator(this, function(_c2) {
        switch (_c2.label) {
          case 0:
            _c2.trys.push([0, 2, 3, 5]);
            return [4, client.handleRedirectCallback(url)];
          case 1:
            return [2, _c2.sent()];
          case 2:
            error_6 = _c2.sent();
            throw tokenError(error_6);
          case 3:
            _a2 = dispatch;
            _b2 = {
              type: "HANDLE_REDIRECT_COMPLETE"
            };
            return [4, client.getUser()];
          case 4:
            _a2.apply(void 0, [(_b2.user = _c2.sent(), _b2)]);
            return [
              7
              /*endfinally*/
            ];
          case 5:
            return [
              2
              /*return*/
            ];
        }
      });
    });
  }, [client]);
  var getDpopNonce = useCallback(function(id) {
    return client.getDpopNonce(id);
  }, [client]);
  var setDpopNonce = useCallback(function(nonce, id) {
    return client.setDpopNonce(nonce, id);
  }, [client]);
  var generateDpopProof = useCallback(function(params) {
    return client.generateDpopProof(params);
  }, [client]);
  var createFetcher = useCallback(function(config) {
    return client.createFetcher(config);
  }, [client]);
  var contextValue = useMemo(function() {
    return __assign(__assign({}, state), { getAccessTokenSilently, getAccessTokenWithPopup, getIdTokenClaims, exchangeToken, loginWithRedirect, loginWithPopup, connectAccountWithRedirect, logout, handleRedirectCallback, getDpopNonce, setDpopNonce, generateDpopProof, createFetcher });
  }, [
    state,
    getAccessTokenSilently,
    getAccessTokenWithPopup,
    getIdTokenClaims,
    exchangeToken,
    loginWithRedirect,
    loginWithPopup,
    connectAccountWithRedirect,
    logout,
    handleRedirectCallback,
    getDpopNonce,
    setDpopNonce,
    generateDpopProof,
    createFetcher
  ]);
  return React__default.createElement(context.Provider, { value: contextValue }, children);
};
var useAuth0$1 = function(context) {
  if (context === void 0) {
    context = Auth0Context;
  }
  return useContext(context);
};
function cn(...inputs) {
  return twMerge(clsx(inputs));
}
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive uppercase font-mono font-medium",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60",
        outline: "border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/50",
        link: "text-primary underline-offset-4 hover:underline"
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        sm: "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-sm": "size-8",
        "icon-lg": "size-10"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);
function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}) {
  const Comp = asChild ? Slot : "button";
  return /* @__PURE__ */ jsx(
    Comp,
    {
      "data-slot": "button",
      "data-variant": variant,
      "data-size": size,
      className: cn(buttonVariants({ variant, size, className })),
      ...props
    }
  );
}
function Sheet({ ...props }) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Root, { "data-slot": "sheet", ...props });
}
function SheetTrigger({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Trigger, { "data-slot": "sheet-trigger", ...props });
}
function SheetClose({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Close, { "data-slot": "sheet-close", ...props });
}
function SheetPortal({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Portal, { "data-slot": "sheet-portal", ...props });
}
function SheetOverlay({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SheetPrimitive.Overlay,
    {
      "data-slot": "sheet-overlay",
      className: cn(
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50",
        className
      ),
      ...props
    }
  );
}
function SheetContent({
  className,
  children,
  side = "right",
  ...props
}) {
  return /* @__PURE__ */ jsxs(SheetPortal, { children: [
    /* @__PURE__ */ jsx(SheetOverlay, {}),
    /* @__PURE__ */ jsxs(
      SheetPrimitive.Content,
      {
        "data-slot": "sheet-content",
        className: cn(
          "bg-background data-[state=open]:animate-in data-[state=closed]:animate-out fixed z-50 flex flex-col gap-4 shadow-lg transition ease-in-out data-[state=closed]:duration-300 data-[state=open]:duration-500",
          side === "right" && "data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm",
          side === "left" && "data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm",
          side === "top" && "data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top inset-x-0 top-0 h-auto border-b",
          side === "bottom" && "data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom inset-x-0 bottom-0 h-auto border-t",
          className
        ),
        ...props,
        children: [
          children,
          /* @__PURE__ */ jsxs(SheetPrimitive.Close, { className: "ring-offset-background focus:ring-ring data-[state=open]:bg-secondary absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none", children: [
            /* @__PURE__ */ jsx(X$1, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { className: "sr-only", children: "Close" })
          ] })
        ]
      }
    )
  ] });
}
function SheetHeader({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sheet-header",
      className: cn("flex flex-col gap-1.5 p-4", className),
      ...props
    }
  );
}
function SheetFooter({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sheet-footer",
      className: cn("mt-auto flex flex-col gap-2 p-4", className),
      ...props
    }
  );
}
function SheetTitle({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SheetPrimitive.Title,
    {
      "data-slot": "sheet-title",
      className: cn("text-foreground font-semibold", className),
      ...props
    }
  );
}
function SheetDescription({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SheetPrimitive.Description,
    {
      "data-slot": "sheet-description",
      className: cn("text-muted-foreground text-sm", className),
      ...props
    }
  );
}
function TooltipProvider({
  delayDuration = 0,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    TooltipPrimitive.Provider,
    {
      "data-slot": "tooltip-provider",
      delayDuration,
      ...props
    }
  );
}
function Tooltip({
  ...props
}) {
  return /* @__PURE__ */ jsx(TooltipProvider, { children: /* @__PURE__ */ jsx(TooltipPrimitive.Root, { "data-slot": "tooltip", ...props }) });
}
function TooltipTrigger({
  ...props
}) {
  return /* @__PURE__ */ jsx(TooltipPrimitive.Trigger, { "data-slot": "tooltip-trigger", ...props });
}
function TooltipContent({
  className,
  sideOffset = 0,
  children,
  ...props
}) {
  return /* @__PURE__ */ jsx(TooltipPrimitive.Portal, { children: /* @__PURE__ */ jsxs(
    TooltipPrimitive.Content,
    {
      "data-slot": "tooltip-content",
      sideOffset,
      className: cn(
        "bg-foreground text-background animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 w-fit origin-(--radix-tooltip-content-transform-origin) rounded-md px-3 py-1.5 text-xs text-balance",
        className
      ),
      ...props,
      children: [
        children,
        /* @__PURE__ */ jsx(TooltipPrimitive.Arrow, { className: "bg-foreground fill-foreground z-50 size-2.5 translate-y-[calc(-50%_-_2px)] rotate-45 rounded-[2px]" })
      ]
    }
  ) });
}
const MOBILE_BREAKPOINT = 768;
function subscribe(callback) {
  const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
  mql.addEventListener("change", callback);
  return () => mql.removeEventListener("change", callback);
}
function getSnapshot() {
  return window.innerWidth < MOBILE_BREAKPOINT;
}
function getServerSnapshot() {
  return false;
}
function useIsMobile() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
const useUISettings = create()(
  persist(
    (set2) => ({
      leftSidebarOpen: true,
      setLeftSidebarOpen: (open) => set2({ leftSidebarOpen: open }),
      toggleLeftSidebar: () => set2((state) => ({ leftSidebarOpen: !state.leftSidebarOpen })),
      rightSidebarTab: null,
      setRightSidebarTab: (tab) => set2({ rightSidebarTab: tab }),
      toggleRightSidebarTab: (tab) => set2((state) => ({
        rightSidebarTab: state.rightSidebarTab === tab ? null : tab
      })),
      // Default to dark as it's a developer tool
      theme: "dark",
      setTheme: (theme) => set2({ theme }),
      _hasHydrated: false,
      setHasHydrated: (hydrated) => set2({ _hasHydrated: hydrated })
    }),
    {
      name: "airweave-ui-settings",
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
      partialize: (state) => ({
        leftSidebarOpen: state.leftSidebarOpen,
        rightSidebarTab: state.rightSidebarTab,
        theme: state.theme
      })
    }
  )
);
function useUISettingsHydrated() {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const unsubscribe = useUISettings.subscribe(
      (state) => setHydrated(state._hasHydrated)
    );
    setHydrated(useUISettings.getState()._hasHydrated);
    return unsubscribe;
  }, []);
  return hydrated;
}
const RIGHT_SIDEBAR_WIDTH = "20rem";
const RIGHT_SIDEBAR_TAB_WIDTH = "3rem";
const RightSidebarContext = React.createContext(null);
function useRightSidebar() {
  const context = React.useContext(RightSidebarContext);
  if (!context) {
    throw new Error(
      "useRightSidebar must be used within a RightSidebarProvider."
    );
  }
  return context;
}
function useRightSidebarContent(content) {
  const { setContent } = useRightSidebar();
  const contentRef = React.useRef(content);
  React.useLayoutEffect(() => {
    contentRef.current = content;
  });
  React.useEffect(() => {
    setContent(contentRef.current);
    return () => {
      setContent({});
    };
  }, [setContent]);
}
function RightSidebarProvider({
  children,
  className,
  style,
  ...props
}) {
  const { rightSidebarTab, setRightSidebarTab, toggleRightSidebarTab } = useUISettings();
  const [content, setContent] = React.useState({});
  const activeTab = rightSidebarTab;
  const setActiveTab = setRightSidebarTab;
  const toggleTab = React.useCallback(
    (tab) => {
      toggleRightSidebarTab(tab);
    },
    [toggleRightSidebarTab]
  );
  const contextValue = React.useMemo(
    () => ({
      activeTab,
      setActiveTab,
      toggleTab,
      content,
      setContent
    }),
    [activeTab, setActiveTab, toggleTab, content, setContent]
  );
  return /* @__PURE__ */ jsx(RightSidebarContext.Provider, { value: contextValue, children: /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 0, children: /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "right-sidebar-wrapper",
      style: {
        "--right-sidebar-width": RIGHT_SIDEBAR_WIDTH,
        "--right-sidebar-tab-width": RIGHT_SIDEBAR_TAB_WIDTH,
        ...style
      },
      className: cn("flex min-h-svh w-full", className),
      ...props,
      children
    }
  ) }) });
}
const tabs = [
  { id: "docs", label: "Docs", icon: /* @__PURE__ */ jsx(BookOpen, { className: "size-5" }) },
  { id: "code", label: "Code", icon: /* @__PURE__ */ jsx(CodeXml, { className: "size-5" }) },
  { id: "help", label: "Help", icon: /* @__PURE__ */ jsx(CircleQuestionMark, { className: "size-5" }) }
];
function RightSidebarTabs({
  className,
  ...props
}) {
  const { activeTab, toggleTab } = useRightSidebar();
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "right-sidebar-tabs",
      className: cn(
        "bg-sidebar fixed inset-y-0 right-0 z-10 hidden w-(--right-sidebar-tab-width) flex-col items-center py-4 md:flex",
        className
      ),
      ...props,
      children: /* @__PURE__ */ jsx("div", { className: "flex flex-col gap-2", children: tabs.map((tab) => /* @__PURE__ */ jsxs(
        Button,
        {
          size: "icon",
          className: cn(
            "h-auto w-10 flex-col rounded-lg bg-transparent px-4 py-2 font-mono text-xs text-slate-50 uppercase transition-colors hover:bg-white/10",
            activeTab === tab.id && "bg-sidebar-accent text-sidebar-accent-foreground"
          ),
          onClick: () => toggleTab(tab.id),
          "aria-pressed": activeTab === tab.id,
          children: [
            tab.icon,
            /* @__PURE__ */ jsx("span", { children: tab.label })
          ]
        },
        tab.id
      )) })
    }
  );
}
function RightSidebarPanel({
  className,
  ...props
}) {
  const { activeTab, content } = useRightSidebar();
  const currentContent = activeTab ? content[activeTab] : null;
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(
      "div",
      {
        "data-slot": "right-sidebar-tab-spacer",
        className: "hidden w-(--right-sidebar-tab-width) shrink-0 md:block"
      }
    ),
    /* @__PURE__ */ jsx(
      "div",
      {
        "data-slot": "right-sidebar-panel-spacer",
        className: cn(
          "hidden shrink-0 transition-[width] duration-200 ease-linear md:block",
          activeTab ? "w-(--right-sidebar-width)" : "w-0"
        )
      }
    ),
    /* @__PURE__ */ jsx(
      "div",
      {
        "data-slot": "right-sidebar-panel",
        "data-state": activeTab ? "open" : "closed",
        className: cn(
          "fixed inset-y-0 z-10 hidden h-svh w-(--right-sidebar-width) text-slate-100 transition-[right] duration-200 ease-linear md:block",
          activeTab ? "right-(--right-sidebar-tab-width)" : "right-[calc(var(--right-sidebar-width)*-1)]",
          className
        ),
        ...props,
        children: /* @__PURE__ */ jsx("div", { className: "flex h-full flex-col py-2.5", children: /* @__PURE__ */ jsx("div", { className: "flex-1 overflow-auto p-4", children: currentContent || /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-sm", children: "No content available for this tab." }) }) })
      }
    )
  ] });
}
const mobileTabs = [
  { id: "app", label: "App", icon: /* @__PURE__ */ jsx(LayoutGrid, { className: "size-5" }) },
  { id: "docs", label: "Docs", icon: /* @__PURE__ */ jsx(BookOpen, { className: "size-5" }) },
  { id: "code", label: "Code", icon: /* @__PURE__ */ jsx(CodeXml, { className: "size-5" }) },
  { id: "help", label: "Help", icon: /* @__PURE__ */ jsx(CircleQuestionMark, { className: "size-5" }) }
];
function MobileBottomNav({ className, ...props }) {
  const { activeTab, setActiveTab } = useRightSidebar();
  const handleTabClick = (tabId) => {
    if (tabId === "app") {
      setActiveTab(null);
    } else {
      setActiveTab(tabId);
    }
  };
  const currentTab = activeTab || "app";
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "mobile-bottom-nav",
      className: cn(
        "bg-sidebar fixed inset-x-0 bottom-0 z-50 flex h-16 items-center justify-around border-t md:hidden",
        className
      ),
      ...props,
      children: mobileTabs.map((tab) => /* @__PURE__ */ jsxs(
        "button",
        {
          type: "button",
          className: cn(
            "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs transition-colors",
            currentTab === tab.id ? "text-sidebar-primary" : "text-muted-foreground hover:text-foreground"
          ),
          onClick: () => handleTabClick(tab.id),
          "aria-pressed": currentTab === tab.id,
          children: [
            tab.icon,
            /* @__PURE__ */ jsx("span", { children: tab.label })
          ]
        },
        tab.id
      ))
    }
  );
}
function MobileRightSidebarSheet({
  className,
  ...props
}) {
  const { activeTab, setActiveTab, content } = useRightSidebar();
  const isMobile = useIsMobile();
  const currentContent = activeTab ? content[activeTab] : null;
  const isOpen = activeTab !== null;
  const handleOpenChange = (open) => {
    if (!open) {
      setActiveTab(null);
    }
  };
  if (!isMobile) {
    return null;
  }
  return /* @__PURE__ */ jsx(Sheet, { open: isOpen, onOpenChange: handleOpenChange, ...props, children: /* @__PURE__ */ jsxs(
    SheetContent,
    {
      side: "bottom",
      className: cn("h-[70vh] rounded-t-xl", className),
      children: [
        /* @__PURE__ */ jsx(SheetHeader, { className: "border-b pb-4", children: /* @__PURE__ */ jsx(SheetTitle, { className: "capitalize", children: activeTab || "Panel" }) }),
        /* @__PURE__ */ jsx("div", { className: "flex-1 overflow-auto py-4", children: currentContent || /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-sm", children: "No content available for this tab." }) })
      ]
    }
  ) });
}
function AppRightSidebar() {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(RightSidebarPanel, {}),
    /* @__PURE__ */ jsx(RightSidebarTabs, {}),
    /* @__PURE__ */ jsx(MobileBottomNav, {}),
    /* @__PURE__ */ jsx(MobileRightSidebarSheet, {})
  ] });
}
const SIDEBAR_WIDTH = "16rem";
const SIDEBAR_WIDTH_MOBILE = "18rem";
const SIDEBAR_WIDTH_ICON = "3rem";
const SIDEBAR_KEYBOARD_SHORTCUT = "b";
const SidebarContext = React.createContext(null);
function useSidebar() {
  const context = React.useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider.");
  }
  return context;
}
function SidebarProvider({
  defaultOpen,
  open: openProp,
  onOpenChange: setOpenProp,
  className,
  style,
  children,
  ...props
}) {
  const isMobile = useIsMobile();
  const [openMobile, setOpenMobile] = React.useState(false);
  const { leftSidebarOpen, setLeftSidebarOpen } = useUISettings();
  const open = openProp ?? (defaultOpen !== void 0 ? defaultOpen : leftSidebarOpen);
  const setOpen = React.useCallback(
    (value) => {
      const openState = typeof value === "function" ? value(leftSidebarOpen) : value;
      if (setOpenProp) {
        setOpenProp(openState);
      }
      setLeftSidebarOpen(openState);
    },
    [setOpenProp, leftSidebarOpen, setLeftSidebarOpen]
  );
  const toggleSidebar = React.useCallback(() => {
    return isMobile ? setOpenMobile((open2) => !open2) : setOpen((open2) => !open2);
  }, [isMobile, setOpen, setOpenMobile]);
  React.useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === SIDEBAR_KEYBOARD_SHORTCUT && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleSidebar]);
  const state = open ? "expanded" : "collapsed";
  const contextValue = React.useMemo(
    () => ({
      state,
      open,
      setOpen,
      isMobile,
      openMobile,
      setOpenMobile,
      toggleSidebar
    }),
    [state, open, setOpen, isMobile, openMobile, setOpenMobile, toggleSidebar]
  );
  return /* @__PURE__ */ jsx(SidebarContext.Provider, { value: contextValue, children: /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 0, children: /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sidebar-wrapper",
      style: {
        "--sidebar-width": SIDEBAR_WIDTH,
        "--sidebar-width-icon": SIDEBAR_WIDTH_ICON,
        ...style
      },
      className: cn(
        "group/sidebar-wrapper has-data-[variant=inset]:bg-sidebar flex min-h-svh w-full",
        className
      ),
      ...props,
      children
    }
  ) }) });
}
function Sidebar({
  side = "left",
  variant = "sidebar",
  collapsible = "offcanvas",
  className,
  children,
  ...props
}) {
  const { isMobile, state, openMobile, setOpenMobile } = useSidebar();
  if (collapsible === "none") {
    return /* @__PURE__ */ jsx(
      "div",
      {
        "data-slot": "sidebar",
        className: cn(
          "bg-sidebar text-sidebar-foreground flex h-full w-(--sidebar-width) flex-col",
          className
        ),
        ...props,
        children
      }
    );
  }
  if (isMobile) {
    return /* @__PURE__ */ jsx(Sheet, { open: openMobile, onOpenChange: setOpenMobile, ...props, children: /* @__PURE__ */ jsxs(
      SheetContent,
      {
        "data-sidebar": "sidebar",
        "data-slot": "sidebar",
        "data-mobile": "true",
        className: "bg-sidebar text-sidebar-foreground w-(--sidebar-width) p-0 [&>button]:hidden",
        style: {
          "--sidebar-width": SIDEBAR_WIDTH_MOBILE
        },
        side,
        children: [
          /* @__PURE__ */ jsxs(SheetHeader, { className: "sr-only", children: [
            /* @__PURE__ */ jsx(SheetTitle, { children: "Sidebar" }),
            /* @__PURE__ */ jsx(SheetDescription, { children: "Displays the mobile sidebar." })
          ] }),
          /* @__PURE__ */ jsx("div", { className: "flex h-full w-full flex-col", children })
        ]
      }
    ) });
  }
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: "group peer text-sidebar-foreground hidden md:block",
      "data-state": state,
      "data-collapsible": state === "collapsed" ? collapsible : "",
      "data-variant": variant,
      "data-side": side,
      "data-slot": "sidebar",
      children: [
        /* @__PURE__ */ jsx(
          "div",
          {
            "data-slot": "sidebar-gap",
            className: cn(
              "relative w-(--sidebar-width) bg-transparent transition-[width] duration-200 ease-linear",
              "group-data-[collapsible=offcanvas]:w-0",
              "group-data-[side=right]:rotate-180",
              variant === "floating" || variant === "inset" ? "group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4)))]" : "group-data-[collapsible=icon]:w-(--sidebar-width-icon)"
            )
          }
        ),
        /* @__PURE__ */ jsx(
          "div",
          {
            "data-slot": "sidebar-container",
            className: cn(
              "fixed inset-y-0 z-10 hidden h-svh w-(--sidebar-width) transition-[left,right,width] duration-200 ease-linear md:flex",
              side === "left" ? "left-0 group-data-[collapsible=offcanvas]:left-[calc(var(--sidebar-width)*-1)]" : "right-0 group-data-[collapsible=offcanvas]:right-[calc(var(--sidebar-width)*-1)]",
              variant === "floating" || variant === "inset" ? "p-2 group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4))+2px)]" : "group-data-[collapsible=icon]:w-(--sidebar-width-icon)",
              className
            ),
            ...props,
            children: /* @__PURE__ */ jsx(
              "div",
              {
                "data-sidebar": "sidebar",
                "data-slot": "sidebar-inner",
                className: "bg-sidebar group-data-[variant=floating]:border-sidebar-border flex h-full w-full flex-col group-data-[variant=floating]:rounded-lg group-data-[variant=floating]:border group-data-[variant=floating]:shadow-sm",
                children
              }
            )
          }
        )
      ]
    }
  );
}
function SidebarTrigger({
  className,
  onClick,
  ...props
}) {
  const { toggleSidebar } = useSidebar();
  return /* @__PURE__ */ jsxs(
    Button,
    {
      "data-sidebar": "trigger",
      "data-slot": "sidebar-trigger",
      variant: "ghost",
      size: "icon",
      className: cn("size-7", className),
      onClick: (event) => {
        onClick?.(event);
        toggleSidebar();
      },
      ...props,
      children: [
        /* @__PURE__ */ jsx(PanelLeft, {}),
        /* @__PURE__ */ jsx("span", { className: "sr-only", children: "Toggle Sidebar" })
      ]
    }
  );
}
function SidebarRail({ className, ...props }) {
  const { toggleSidebar } = useSidebar();
  return /* @__PURE__ */ jsx(
    "button",
    {
      "data-sidebar": "rail",
      "data-slot": "sidebar-rail",
      "aria-label": "Toggle Sidebar",
      tabIndex: -1,
      onClick: toggleSidebar,
      title: "Toggle Sidebar",
      className: cn(
        "hover:after:bg-sidebar-border absolute inset-y-0 z-20 hidden w-4 -translate-x-1/2 transition-all ease-linear group-data-[side=left]:-right-4 group-data-[side=right]:left-0 after:absolute after:inset-y-0 after:left-1/2 after:w-[2px] sm:flex",
        "in-data-[side=left]:cursor-w-resize in-data-[side=right]:cursor-e-resize",
        "[[data-side=left][data-state=collapsed]_&]:cursor-e-resize [[data-side=right][data-state=collapsed]_&]:cursor-w-resize",
        "hover:group-data-[collapsible=offcanvas]:bg-sidebar group-data-[collapsible=offcanvas]:translate-x-0 group-data-[collapsible=offcanvas]:after:left-full",
        "[[data-side=left][data-collapsible=offcanvas]_&]:-right-2",
        "[[data-side=right][data-collapsible=offcanvas]_&]:-left-2",
        className
      ),
      ...props
    }
  );
}
function SidebarInset({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "main",
    {
      "data-slot": "sidebar-inset",
      className: cn(
        "bg-background relative flex w-full flex-1 flex-col",
        "md:peer-data-[variant=inset]:m-2 md:peer-data-[variant=inset]:ml-0 md:peer-data-[variant=inset]:rounded-xl md:peer-data-[variant=inset]:shadow-sm md:peer-data-[variant=inset]:peer-data-[state=collapsed]:ml-2",
        className
      ),
      ...props
    }
  );
}
function SidebarHeader({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sidebar-header",
      "data-sidebar": "header",
      className: cn("flex flex-col gap-2 p-2", className),
      ...props
    }
  );
}
function SidebarFooter({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sidebar-footer",
      "data-sidebar": "footer",
      className: cn("flex flex-col gap-2 p-2", className),
      ...props
    }
  );
}
function SidebarContent({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sidebar-content",
      "data-sidebar": "content",
      className: cn(
        "flex min-h-0 flex-1 flex-col gap-2 overflow-auto group-data-[collapsible=icon]:overflow-hidden",
        className
      ),
      ...props
    }
  );
}
function SidebarGroup({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sidebar-group",
      "data-sidebar": "group",
      className: cn("relative flex w-full min-w-0 flex-col p-2", className),
      ...props
    }
  );
}
function SidebarGroupContent({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "sidebar-group-content",
      "data-sidebar": "group-content",
      className: cn("w-full text-sm", className),
      ...props
    }
  );
}
function SidebarMenu({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "ul",
    {
      "data-slot": "sidebar-menu",
      "data-sidebar": "menu",
      className: cn("flex w-full min-w-0 flex-col gap-1", className),
      ...props
    }
  );
}
function SidebarMenuItem({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "li",
    {
      "data-slot": "sidebar-menu-item",
      "data-sidebar": "menu-item",
      className: cn("group/menu-item relative", className),
      ...props
    }
  );
}
const sidebarMenuButtonVariants = cva(
  "peer/menu-button flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left text-sm outline-hidden ring-sidebar-ring transition-[width,height,padding] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 group-has-data-[sidebar=menu-action]/menu-item:pr-8 aria-disabled:pointer-events-none aria-disabled:opacity-50 data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground data-[state=open]:hover:bg-sidebar-accent data-[state=open]:hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-2! [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        outline: "bg-background shadow-[0_0_0_1px_hsl(var(--sidebar-border))] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:shadow-[0_0_0_1px_hsl(var(--sidebar-accent))]"
      },
      size: {
        default: "h-8 text-sm",
        sm: "h-7 text-xs",
        lg: "h-12 text-sm group-data-[collapsible=icon]:p-0!"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);
function SidebarMenuButton({
  asChild = false,
  isActive = false,
  variant = "default",
  size = "default",
  tooltip,
  className,
  ...props
}) {
  const Comp = asChild ? Slot : "button";
  const { isMobile, state } = useSidebar();
  const button = /* @__PURE__ */ jsx(
    Comp,
    {
      "data-slot": "sidebar-menu-button",
      "data-sidebar": "menu-button",
      "data-size": size,
      "data-active": isActive,
      className: cn(sidebarMenuButtonVariants({ variant, size }), className),
      ...props
    }
  );
  if (!tooltip) {
    return button;
  }
  if (typeof tooltip === "string") {
    tooltip = {
      children: tooltip
    };
  }
  return /* @__PURE__ */ jsxs(Tooltip, { children: [
    /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: button }),
    /* @__PURE__ */ jsx(
      TooltipContent,
      {
        side: "right",
        align: "center",
        hidden: state !== "collapsed" || isMobile,
        ...tooltip
      }
    )
  ] });
}
function Avatar({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    AvatarPrimitive.Root,
    {
      "data-slot": "avatar",
      className: cn(
        "relative flex size-8 shrink-0 overflow-hidden rounded-full",
        className
      ),
      ...props
    }
  );
}
function AvatarImage({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    AvatarPrimitive.Image,
    {
      "data-slot": "avatar-image",
      className: cn("aspect-square size-full", className),
      ...props
    }
  );
}
function AvatarFallback({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    AvatarPrimitive.Fallback,
    {
      "data-slot": "avatar-fallback",
      className: cn(
        "bg-muted flex size-full items-center justify-center rounded-full",
        className
      ),
      ...props
    }
  );
}
function DropdownMenu({
  ...props
}) {
  return /* @__PURE__ */ jsx(DropdownMenuPrimitive.Root, { "data-slot": "dropdown-menu", ...props });
}
function DropdownMenuTrigger({
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DropdownMenuPrimitive.Trigger,
    {
      "data-slot": "dropdown-menu-trigger",
      ...props
    }
  );
}
function DropdownMenuContent({
  className,
  sideOffset = 4,
  ...props
}) {
  return /* @__PURE__ */ jsx(DropdownMenuPrimitive.Portal, { children: /* @__PURE__ */ jsx(
    DropdownMenuPrimitive.Content,
    {
      "data-slot": "dropdown-menu-content",
      sideOffset,
      className: cn(
        "bg-popover text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 max-h-(--radix-dropdown-menu-content-available-height) min-w-[8rem] origin-(--radix-dropdown-menu-content-transform-origin) overflow-x-hidden overflow-y-auto rounded-md border p-1 shadow-md",
        className
      ),
      ...props
    }
  ) });
}
function DropdownMenuGroup({
  ...props
}) {
  return /* @__PURE__ */ jsx(DropdownMenuPrimitive.Group, { "data-slot": "dropdown-menu-group", ...props });
}
function DropdownMenuItem({
  className,
  inset,
  variant = "default",
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DropdownMenuPrimitive.Item,
    {
      "data-slot": "dropdown-menu-item",
      "data-inset": inset,
      "data-variant": variant,
      className: cn(
        "focus:bg-accent focus:text-accent-foreground data-[variant=destructive]:text-destructive data-[variant=destructive]:focus:bg-destructive/10 dark:data-[variant=destructive]:focus:bg-destructive/20 data-[variant=destructive]:focus:text-destructive data-[variant=destructive]:*:[svg]:!text-destructive [&_svg:not([class*='text-'])]:text-muted-foreground relative flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[inset]:pl-8 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className
      ),
      ...props
    }
  );
}
function DropdownMenuLabel({
  className,
  inset,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DropdownMenuPrimitive.Label,
    {
      "data-slot": "dropdown-menu-label",
      "data-inset": inset,
      className: cn(
        "px-2 py-1.5 text-sm font-medium data-[inset]:pl-8",
        className
      ),
      ...props
    }
  );
}
function DropdownMenuSeparator({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DropdownMenuPrimitive.Separator,
    {
      "data-slot": "dropdown-menu-separator",
      className: cn("bg-border -mx-1 my-1 h-px", className),
      ...props
    }
  );
}
function DropdownMenuShortcut({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "span",
    {
      "data-slot": "dropdown-menu-shortcut",
      className: cn(
        "text-muted-foreground ml-auto text-xs tracking-widest",
        className
      ),
      ...props
    }
  );
}
function DropdownMenuSub({
  ...props
}) {
  return /* @__PURE__ */ jsx(DropdownMenuPrimitive.Sub, { "data-slot": "dropdown-menu-sub", ...props });
}
function DropdownMenuSubTrigger({
  className,
  inset,
  children,
  ...props
}) {
  return /* @__PURE__ */ jsxs(
    DropdownMenuPrimitive.SubTrigger,
    {
      "data-slot": "dropdown-menu-sub-trigger",
      "data-inset": inset,
      className: cn(
        "focus:bg-accent focus:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground [&_svg:not([class*='text-'])]:text-muted-foreground flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[inset]:pl-8 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className
      ),
      ...props,
      children: [
        children,
        /* @__PURE__ */ jsx(ChevronRight, { className: "ml-auto size-4" })
      ]
    }
  );
}
function DropdownMenuSubContent({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    DropdownMenuPrimitive.SubContent,
    {
      "data-slot": "dropdown-menu-sub-content",
      className: cn(
        "bg-popover text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 min-w-[8rem] origin-(--radix-dropdown-menu-content-transform-origin) overflow-hidden rounded-md border p-1 shadow-lg",
        className
      ),
      ...props
    }
  );
}
const themeOptions = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor }
];
const API_BASE_URL = "https://api.airweave.ai";
function getAuthHeaders(token, organizationId) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...organizationId && { "X-Organization-ID": organizationId }
  };
}
async function parseErrorResponse(response, defaultMessage) {
  try {
    const errorText = await response.text();
    const parsed = JSON.parse(errorText);
    return parsed.detail || parsed.message || defaultMessage;
  } catch {
    return defaultMessage;
  }
}
async function fetchOrganizations(token) {
  const response = await fetch(`${API_BASE_URL}/organizations/`, {
    method: "GET",
    headers: getAuthHeaders(token)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch organizations"
    );
    throw new Error(message);
  }
  return response.json();
}
async function createOrganization(token, data) {
  const response = await fetch(`${API_BASE_URL}/organizations/`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create organization"
    );
    throw new Error(message);
  }
  return response.json();
}
async function createCheckoutSession(token, data, yearly = false) {
  const endpoint = yearly ? `${API_BASE_URL}/billing/yearly/checkout-session` : `${API_BASE_URL}/billing/checkout-session`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create checkout session"
    );
    throw new Error(message);
  }
  return response.json();
}
function getRedirectUrl() {
  if (typeof window === "undefined") return "";
  const origin = window.location.origin;
  if (origin.includes("localhost") || origin.includes("127.0.0.1")) {
    return "https://app.airweave.ai/callback";
  }
  return origin;
}
const LOCAL_DEV_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IlkzN3F5b1NieEIzbzhFdlQtZ2tjVSJ9.eyJodHRwczovL2FwcC5haXJ3ZWF2ZS5haS9lbWFpbCI6ImFuYW5kQGNob3dkaGFyeS5vcmciLCJpc3MiOiJodHRwczovL2FpcndlYXZlLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTE3NDgwNDU1MDk5NTEzMDkyMCIsImF1ZCI6WyJodHRwczovL2FwcC5haXJ3ZWF2ZS5haS8iLCJodHRwczovL2FpcndlYXZlLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3Njc1NTgxODAsImV4cCI6MTc2NzY0NDU4MCwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCIsImF6cCI6ImpYeUxSV1I5bGcwa1pRdlZqcEoyWW1pU1luMVV0VVN3In0.YTIs-f_pgS1F6PIYijxXnAHxTF6ieJBTCWNupLdIh8mhxP3UGw2bN5awPT_5JmR1YjOtGRpzLY5unaH9WwdcDdg_UqsZzSi7AhLQxv_SUEcu3dVSx34mKsMk6Gfbzyk3FxOlybHBth5Hk1-Z4-ablU3hmPYqxEzQoPsG8dNHe2YUPKA_2F37E_Fy3QtsP4FULBBjNaMQIFO1dBS381Yn2RvsgNUfWN54kUjgiNeY5bcZeAYWCWS3V0Rsda9qXav1FUg5_qMnx8IO-3aFvSyAB4RAL_xowwhWiEQMYRDMyoDImJyXuO5HqB8pQaRtfzjQtmMto1YVxPgewYE477GMGA";
function isLocalhost() {
  if (typeof window === "undefined") return false;
  const origin = window.location.origin;
  return origin.includes("localhost") || origin.includes("127.0.0.1");
}
const accessToken = isLocalhost() ? LOCAL_DEV_TOKEN : "";
const authEnabled = !accessToken && true;
const authConfig = {
  domain: "airweave.us.auth0.com",
  clientId: "jXyLRWR9lg0kZQvVjpJ2YmiSYn1UtUSw",
  audience: "https://app.airweave.ai/",
  redirectUri: getRedirectUrl(),
  /** Access token for local development (skips Auth0 login) */
  accessToken,
  /** Whether Auth0 authentication is enabled */
  authEnabled
};
const devUser = {
  name: "Anand Chowdhary",
  email: "anand@chowdhary.org",
  picture: ""
};
const queryKeys = {
  organizations: {
    all: ["organizations"]
  },
  apiKeys: {
    all: (orgId) => [orgId, "api-keys"],
    list: (orgId) => [orgId, "api-keys", "list"]
  },
  authProviders: {
    all: (orgId) => [orgId, "auth-providers"],
    list: (orgId) => [orgId, "auth-providers", "list"],
    detail: (orgId, shortName) => [orgId, "auth-providers", "detail", shortName],
    connections: (orgId) => [orgId, "auth-provider-connections"],
    connection: (orgId, id) => [orgId, "auth-provider-connections", id]
  },
  collections: {
    all: (orgId) => [orgId, "collections"],
    list: (orgId) => [orgId, "collections", "list"],
    detail: (orgId, readableId) => [orgId, "collections", "detail", readableId],
    count: (orgId) => [orgId, "collections", "count"]
  },
  sources: {
    all: (orgId) => [orgId, "sources"],
    list: (orgId) => [orgId, "sources", "list"],
    detail: (orgId, shortName) => [orgId, "sources", "detail", shortName]
  },
  sourceConnections: {
    all: (orgId, collectionId) => [orgId, "source-connections", collectionId],
    list: (orgId, collectionId) => [orgId, "source-connections", collectionId, "list"],
    detail: (orgId, id) => [orgId, "source-connections", "detail", id]
  }
};
const LOADING_DELAY_MS = 50;
const LOADING_TIMEOUT_MS = 1e4;
function DataPreloader({ children }) {
  const queryClient2 = useQueryClient();
  const { getAccessTokenSilently } = useAuth0();
  const hasStartedPreloading = useRef(false);
  const [isFetching, setIsFetching] = useState(false);
  const [showLoading, setShowLoading] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const isRestoring = useIsRestoring();
  const hasOrganizationsCache = !isRestoring && queryClient2.getQueryData(queryKeys.organizations.all) !== void 0;
  const isLoading = (isRestoring || isFetching) && !timedOut;
  useEffect(() => {
    if (!isLoading) {
      setShowLoading(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowLoading(true);
    }, LOADING_DELAY_MS);
    return () => clearTimeout(timer);
  }, [isLoading]);
  useEffect(() => {
    if (!isRestoring && !isFetching) return;
    const timeout = setTimeout(() => {
      console.debug("Data preloading timed out after 10s, rendering anyway");
      setTimedOut(true);
    }, LOADING_TIMEOUT_MS);
    return () => clearTimeout(timeout);
  }, [isRestoring, isFetching]);
  useEffect(() => {
    if (isRestoring) return;
    if (hasStartedPreloading.current) return;
    hasStartedPreloading.current = true;
    if (hasOrganizationsCache) {
      return;
    }
    setIsFetching(true);
    const prefetchData = async () => {
      try {
        const token = await getAccessTokenSilently();
        await queryClient2.prefetchQuery({
          queryKey: queryKeys.organizations.all,
          queryFn: () => fetchOrganizations(token),
          staleTime: 1e3 * 60 * 5
        });
      } catch (error) {
        console.debug("Data preloading failed:", error);
      } finally {
        setIsFetching(false);
      }
    };
    prefetchData();
  }, [queryClient2, getAccessTokenSilently, isRestoring, hasOrganizationsCache]);
  if (showLoading) {
    return /* @__PURE__ */ jsx("div", { className: "bg-background flex h-screen w-screen items-center justify-center", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center gap-4", children: [
      /* @__PURE__ */ jsx("div", { className: "border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Loading..." })
    ] }) });
  }
  if (isLoading) {
    return null;
  }
  return /* @__PURE__ */ jsx(Fragment, { children });
}
const AuthContext = createContext(null);
function useAuth0() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth0 must be used within an AuthProvider");
  }
  return context;
}
function Auth0Bridge({ children }) {
  const auth0 = useAuth0$1();
  return /* @__PURE__ */ jsx(AuthContext.Provider, { value: auth0, children });
}
function AuthProvider({ children }) {
  const devAuthValue = useMemo(
    () => ({
      isAuthenticated: true,
      isLoading: false,
      user: devUser,
      logout: () => {
      },
      loginWithRedirect: () => {
      },
      getAccessTokenSilently: async () => authConfig.accessToken
    }),
    []
  );
  if (typeof window === "undefined") {
    return /* @__PURE__ */ jsx(Fragment, { children });
  }
  if (!authConfig.authEnabled) {
    return /* @__PURE__ */ jsx(AuthContext.Provider, { value: devAuthValue, children });
  }
  return /* @__PURE__ */ jsx(
    Auth0Provider,
    {
      domain: authConfig.domain,
      clientId: authConfig.clientId,
      authorizationParams: {
        redirect_uri: getRedirectUrl(),
        audience: authConfig.audience,
        scope: "openid profile email"
      },
      cacheLocation: "localstorage",
      children: /* @__PURE__ */ jsx(Auth0Bridge, { children })
    }
  );
}
function AuthGuard({ children }) {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  if (!authConfig.authEnabled) {
    return /* @__PURE__ */ jsx(DataPreloader, { children });
  }
  if (isLoading) {
    return /* @__PURE__ */ jsx("div", { className: "bg-background flex h-screen w-screen items-center justify-center", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center gap-4", children: [
      /* @__PURE__ */ jsx("div", { className: "border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Loading..." })
    ] }) });
  }
  if (!isAuthenticated) {
    loginWithRedirect();
    return /* @__PURE__ */ jsx("div", { className: "bg-background flex h-screen w-screen items-center justify-center", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center gap-4", children: [
      /* @__PURE__ */ jsx("div", { className: "border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Redirecting to login..." })
    ] }) });
  }
  return /* @__PURE__ */ jsx(DataPreloader, { children });
}
function slugify(text) {
  return text.toLowerCase().replace(/[\s_]+/g, "-").replace(/[^a-z0-9-]/g, "").replace(/-+/g, "-").replace(/^-|-$/g, "");
}
function getShortId(uuid) {
  return uuid.replace(/-/g, "").slice(0, 8);
}
function generateOrgSlug(org) {
  const nameSlug = slugify(org.name);
  const shortId = getShortId(org.id);
  return `${nameSlug}-${shortId}`;
}
function parseOrgIdFromSlug(slug) {
  const match = slug.match(/-([a-f0-9]{8})$/);
  if (!match) return null;
  return match[1];
}
function findOrgBySlug(organizations, slug) {
  const shortId = parseOrgIdFromSlug(slug);
  if (!shortId) return void 0;
  return organizations.find((org) => getShortId(org.id) === shortId);
}
function getPrimaryOrg(organizations) {
  return organizations.find((org) => org.is_primary) || organizations[0];
}
function getInitials(name) {
  return name.split(" ").map((part) => part[0]).join("").toUpperCase().slice(0, 2);
}
function UserAccountDropdown({
  variant = "sidebar",
  className
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const theme = useUISettings((state) => state.theme);
  const setTheme = useUISettings((state) => state.setTheme);
  const { user, logout, getAccessTokenSilently } = useAuth0();
  const orgSlug = params.orgSlug;
  const { data: organizations = [] } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
    staleTime: 1e3 * 60 * 5
  });
  const currentOrg = orgSlug ? findOrgBySlug(organizations, orgSlug) : null;
  const handleLogout = () => {
    logout({
      logoutParams: {
        returnTo: getRedirectUrl()
      }
    });
  };
  const handleSwitchOrg = (org) => {
    const newOrgSlug = generateOrgSlug(org);
    const currentPath = location.pathname;
    const pathAfterOrg = orgSlug ? currentPath.replace(`/${orgSlug}`, "") : "";
    navigate({
      to: `/$orgSlug${pathAfterOrg || "/"}`,
      params: { orgSlug: newOrgSlug }
    });
  };
  const handleCreateOrganization = () => {
    navigate({ to: "/onboarding" });
  };
  const userName = user?.name || user?.email || "User";
  const userAvatar = user?.picture || "";
  const triggerContent = /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(Avatar, { className: "size-5 rounded-full", children: [
      /* @__PURE__ */ jsx(AvatarImage, { src: userAvatar, alt: userName }),
      /* @__PURE__ */ jsx(AvatarFallback, { className: "rounded-full bg-slate-700 text-[60%] font-medium", children: getInitials(userName) })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "grid flex-1 text-left text-sm leading-tight", children: /* @__PURE__ */ jsx("span", { className: "truncate font-medium", children: userName }) })
  ] });
  return /* @__PURE__ */ jsxs(DropdownMenu, { children: [
    /* @__PURE__ */ jsx(DropdownMenuTrigger, { asChild: true, children: variant === "sidebar" ? /* @__PURE__ */ jsx(
      SidebarMenuButton,
      {
        className: cn(
          "data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground",
          className
        ),
        tooltip: userName,
        children: triggerContent
      }
    ) : /* @__PURE__ */ jsx(
      Button,
      {
        variant: "ghost",
        className: cn("-ml-3 h-auto gap-2 px-3 py-2", className),
        children: triggerContent
      }
    ) }),
    /* @__PURE__ */ jsxs(
      DropdownMenuContent,
      {
        side: variant === "sidebar" ? "top" : "bottom",
        align: "start",
        className: "w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg",
        children: [
          organizations.length > 0 && /* @__PURE__ */ jsx(Fragment, { children: /* @__PURE__ */ jsxs(DropdownMenuSub, { children: [
            /* @__PURE__ */ jsxs(DropdownMenuSubTrigger, { children: [
              /* @__PURE__ */ jsx(Building2, {}),
              /* @__PURE__ */ jsx("span", { children: "Switch organization" })
            ] }),
            /* @__PURE__ */ jsxs(DropdownMenuSubContent, { children: [
              organizations.map((org) => /* @__PURE__ */ jsxs(
                DropdownMenuItem,
                {
                  onClick: () => handleSwitchOrg(org),
                  children: [
                    /* @__PURE__ */ jsx(Building2, {}),
                    /* @__PURE__ */ jsx("span", { children: org.name }),
                    currentOrg && org.id === currentOrg.id && /* @__PURE__ */ jsx(Check, { className: "ml-auto size-4" })
                  ]
                },
                org.id
              )),
              /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
              /* @__PURE__ */ jsxs(DropdownMenuItem, { onClick: handleCreateOrganization, children: [
                /* @__PURE__ */ jsx(Plus, {}),
                /* @__PURE__ */ jsx("span", { children: "Create organization" })
              ] })
            ] })
          ] }) }),
          /* @__PURE__ */ jsxs(DropdownMenuSub, { children: [
            /* @__PURE__ */ jsxs(DropdownMenuSubTrigger, { children: [
              /* @__PURE__ */ jsx(Palette, {}),
              /* @__PURE__ */ jsx("span", { children: "Theme" })
            ] }),
            /* @__PURE__ */ jsx(DropdownMenuSubContent, { children: themeOptions.map((option) => /* @__PURE__ */ jsxs(
              DropdownMenuItem,
              {
                onClick: () => setTheme(option.value),
                children: [
                  /* @__PURE__ */ jsx(option.icon, {}),
                  /* @__PURE__ */ jsx("span", { children: option.label }),
                  theme === option.value && /* @__PURE__ */ jsx(Check, { className: "ml-auto size-4" })
                ]
              },
              option.value
            )) })
          ] }),
          /* @__PURE__ */ jsxs(DropdownMenuItem, { variant: "destructive", onClick: handleLogout, children: [
            /* @__PURE__ */ jsx(LogOut, {}),
            /* @__PURE__ */ jsx("span", { children: "Log out" })
          ] })
        ]
      }
    )
  ] });
}
const navItems = [
  {
    title: "Collections",
    to: "/$orgSlug/collections",
    icon: LayoutGrid
  },
  {
    title: "Logs",
    to: "/$orgSlug/logs",
    icon: Terminal
  },
  {
    title: "API Keys",
    to: "/$orgSlug/api-keys",
    icon: Key
  },
  {
    title: "Webhooks",
    to: "/$orgSlug/webhooks",
    icon: Webhook
  },
  {
    title: "Auth Providers",
    to: "/$orgSlug/auth-providers",
    icon: ShieldCheck
  }
];
const useCreateCollectionStore = create()(
  (set2) => ({
    isOpen: false,
    preSelectedSource: null,
    open: () => set2({ isOpen: true, preSelectedSource: null }),
    openWithSource: (shortName, name) => set2({ isOpen: true, preSelectedSource: { shortName, name } }),
    close: () => set2({ isOpen: false }),
    toggle: () => set2((state) => ({ isOpen: !state.isOpen })),
    clearPreSelectedSource: () => set2({ preSelectedSource: null })
  })
);
function AppSidebar() {
  const location = useLocation();
  const params = useParams({ strict: false });
  const orgSlug = params.orgSlug;
  const openCreateCollection = useCreateCollectionStore((s2) => s2.open);
  if (!orgSlug) {
    return null;
  }
  const isActive = (to) => {
    const fullPath = to.replace("$orgSlug", orgSlug);
    return location.pathname.startsWith(fullPath);
  };
  return /* @__PURE__ */ jsxs(Sidebar, { collapsible: "icon", side: "left", className: "py-2", children: [
    /* @__PURE__ */ jsxs(SidebarHeader, { children: [
      /* @__PURE__ */ jsx(SidebarMenu, { children: /* @__PURE__ */ jsx(SidebarMenuItem, { children: /* @__PURE__ */ jsx(
        Button,
        {
          className: "mb-1 flex h-auto w-full justify-start gap-2 py-2 text-slate-100 group-data-[collapsible=icon]:pl-2 hover:bg-slate-100/10 hover:text-slate-100 dark:text-slate-100 dark:hover:text-slate-100",
          size: "sm",
          variant: "ghost",
          asChild: true,
          children: /* @__PURE__ */ jsxs(Link, { to: "/$orgSlug/collections", params: { orgSlug }, children: [
            /* @__PURE__ */ jsxs(
              "svg",
              {
                className: "shrink-0",
                viewBox: "0 0 143 143",
                fill: "none",
                xmlns: "http://www.w3.org/2000/svg",
                children: [
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M89.3854 128.578C79.4165 123.044 66.2502 114.852 60.0707 107.348L59.5432 106.724C58.2836 105.206 56.981 103.72 55.6676 102.299C51.4152 97.6699 46.8614 93.5036 42.146 89.9079C40.2405 88.4546 38.2704 87.055 36.3111 85.7847C35.2991 85.128 34.3302 84.5251 33.4151 83.9761C31.1221 82.6088 28.3338 82.2321 25.7716 82.9534C23.3385 83.6424 21.39 85.2464 20.2596 87.4534C18.0634 91.7381 19.5814 97.0347 23.7046 99.5108C27.0204 101.492 30.2608 103.817 33.3398 106.422C33.7381 106.756 33.8996 107.284 33.7596 107.768C32.6292 111.891 31.4989 118.663 31.0682 121.376C30.1424 127.135 32.9737 132.787 38.0982 135.457L38.2812 135.554C40.5204 136.706 43.1472 136.652 45.3219 135.403C47.4858 134.165 48.853 131.937 48.9822 129.439C49.036 128.363 49.1006 127.286 49.176 126.296C49.219 125.768 49.542 125.337 50.0264 125.165C50.1772 125.111 50.3494 125.079 50.5001 125.079C50.8554 125.079 51.1784 125.219 51.4475 125.488C55.743 129.891 60.3829 133.875 65.2167 137.33C69.8674 140.657 75.3686 142.412 81.139 142.412C83.2383 142.412 85.3376 142.175 87.3938 141.701L87.6199 141.647C90.4943 140.98 92.529 138.73 92.9488 135.791C93.3687 132.852 91.9476 130.02 89.3747 128.589H89.3639L89.3854 128.578Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M142.051 57.8805L142.029 57.7621C141.545 55.2968 139.618 53.4128 137.098 52.9606C134.612 52.5192 132.254 53.5635 130.984 55.6951L130.908 55.8135C126.204 63.8662 119.561 71.3159 111.153 78.0014C108.946 79.7562 106.793 81.6078 104.726 83.5134C103.144 84.9775 100.765 85.2359 98.9452 84.127C97.1474 83.0397 95.3495 81.8447 93.6055 80.5744C89.8268 77.8291 86.1772 74.6533 82.7753 71.1329C80.9989 69.3028 79.298 67.3973 77.6939 65.438C75.5408 62.8219 73.2477 60.2597 70.8685 57.8374C65.8195 52.6915 56.1089 45.6185 53.2453 43.5838C52.8792 43.3362 52.6639 42.9486 52.5993 42.5073C52.5455 42.0659 52.6639 41.6567 52.9546 41.3122C54.774 39.1376 56.4965 36.8876 58.0683 34.6268C59.7369 32.2369 60.286 29.3086 59.5862 26.5957C58.908 23.9581 57.1424 21.8158 54.634 20.5885C50.4139 18.5 45.3972 19.8026 42.7273 23.6351C40.3373 27.0694 37.5167 30.439 34.3732 33.6364C34.0718 33.9378 33.6304 34.0455 33.2213 33.8948C30.0239 32.8505 26.7296 32 23.4461 31.3648C23.2093 31.3218 22.854 31.2572 22.4126 31.2034C15.9102 30.2345 9.61233 33.4857 6.71639 39.2775L6.6195 39.4606C5.68289 41.3338 5.76902 43.5407 6.82405 45.3709C7.90061 47.2226 9.82765 48.4068 11.9592 48.5252C12.9604 48.579 13.9401 48.6436 14.8659 48.7082C15.2966 48.7405 15.6411 48.9881 15.8025 49.3972C15.9533 49.8171 15.8671 50.2477 15.5657 50.5599C11.647 54.5862 8.10515 58.9032 5.0262 63.3925C0.644601 69.7872 -0.981008 77.9153 0.580002 85.688L0.601538 85.8064C1.20441 88.7777 3.55131 90.9093 6.57644 91.2323C9.48315 91.5445 12.1099 90.0266 13.2619 87.3782L13.3265 87.2167C18.1925 75.5683 26.2559 65.2226 37.2907 56.4594C37.8182 56.0503 38.5072 55.9858 39.067 56.298C44.8373 59.4738 50.3601 63.6078 55.4738 68.5923C56.0982 69.1951 56.1089 70.2071 55.5168 70.8315C52.9761 73.5122 50.5862 76.3112 48.4115 79.1749C46.7106 81.4141 47.0335 84.6007 49.1221 86.4416L52.8254 89.7036L52.7824 89.7467C53.3637 90.2634 53.945 90.7802 54.5264 91.2969L55.3123 91.8998C56.4319 92.8902 57.8529 93.3423 59.3386 93.1916C60.8027 93.0409 62.17 92.2658 63.0635 91.0816C64.6353 88.9931 66.3578 86.9584 68.1556 85.0098C68.457 84.676 68.8661 84.5038 69.3075 84.4931C69.7705 84.4931 70.1257 84.6437 70.4164 84.9344C75.3147 89.7682 80.6114 94.0744 86.1772 97.7024C88.3626 99.1234 88.9978 101.966 87.6306 104.183C86.4248 106.153 85.2729 108.199 84.2179 110.244C83.0014 112.624 82.7968 115.444 83.6688 117.963C84.4978 120.385 86.2095 122.291 88.481 123.346C89.7514 123.938 91.0971 124.24 92.4859 124.24C96.0062 124.24 99.182 122.302 100.786 119.158C102.229 116.316 103.919 113.506 105.781 110.836C106.869 109.265 108.86 108.543 110.755 109.028C114.76 110.061 120.143 111.127 123.954 111.848C127.808 112.57 131.619 110.729 133.46 107.284L133.643 106.939C135.021 104.334 135.031 101.212 133.664 98.5959C132.286 95.9584 129.681 94.1713 126.71 93.8268C125.978 93.7407 125.278 93.6546 124.61 93.5684C124.47 93.5469 124.352 93.5254 124.244 93.5038L122.856 93.1809L123.857 92.1581C123.932 92.0828 124.029 91.9859 124.158 91.8998C128.271 88.5086 132.071 84.9021 135.462 81.1772C141.168 74.9009 143.622 66.2023 142.018 57.8805H142.029H142.051Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M56.1506 14.0429C65.0861 19.3396 76.9067 27.0801 82.4833 33.8732C83.14 34.659 83.7967 35.4449 84.4534 36.1985C85.6591 37.5873 85.7991 39.5789 84.7979 41.1292C82.9892 43.9174 80.9115 46.6627 78.6399 49.3003C76.9713 51.2165 76.9067 54.0156 78.4785 55.9534L78.5431 56.0288C78.7261 56.2656 78.9306 56.5132 79.1136 56.75C80.7931 58.8816 82.5801 60.9271 84.4211 62.8433C85.4007 63.8661 86.7249 64.4367 88.1352 64.4367L88.2644 65.2333L88.2429 64.4367C89.707 64.4044 91.1173 63.7584 92.0969 62.6388C94.3362 60.1089 96.4247 57.4498 98.3302 54.7691C99.6329 52.9282 102.13 52.5084 104.025 53.8111C105.963 55.146 107.965 56.4163 109.957 57.5897C112.293 58.957 115.114 59.2153 117.665 58.268C120.249 57.3098 122.262 55.2752 123.156 52.6591C124.555 48.6113 122.757 43.9605 118.882 41.6136C116.255 40.0203 113.65 38.2224 111.174 36.2846C109.882 35.2619 109.333 33.5825 109.796 32C110.937 28.0059 111.981 22.8276 112.648 19.1889C113.337 15.4317 111.647 11.5884 108.439 9.65058L108.062 9.43525C105.371 7.83118 102.087 7.71277 99.2668 9.1123C96.4247 10.5226 94.53 13.2463 94.1855 16.3791L94.1639 16.5728C94.1209 16.9604 93.884 17.2511 93.518 17.3695C93.152 17.4879 92.7859 17.3911 92.5168 17.1327C88.5012 12.848 84.238 8.96157 79.8134 5.57041C73.8708 1.01656 66.2811 -0.878188 58.9928 0.381386L58.6805 0.435234C55.6124 0.973513 53.2547 3.30965 52.6949 6.3886C52.1351 9.43527 53.4915 12.4281 56.1722 14.0106H56.1614L56.1506 14.0429Z",
                      fill: "currentColor"
                    }
                  )
                ]
              }
            ),
            /* @__PURE__ */ jsx("div", { className: "flex grow items-center justify-stretch group-data-[collapsible=icon]:hidden", children: /* @__PURE__ */ jsxs(
              "svg",
              {
                viewBox: "0 0 356 66",
                className: "size-18 h-auto",
                fill: "none",
                xmlns: "http://www.w3.org/2000/svg",
                children: [
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M350.783 25.4493C347.015 20.6063 341.21 18.0454 333.992 18.0454C327.205 18.0454 321.499 20.3343 317.485 24.6665C313.531 28.9324 311.442 34.9364 311.442 42.0219C311.442 49.1073 313.558 55.191 317.572 59.4569C321.599 63.736 327.311 66.005 334.078 66.005C344.64 66.005 352.468 60.3724 354.518 51.3099L354.618 50.8522H344.514L344.427 51.1109C343.538 54.0499 340.281 57.4798 334.084 57.4798C330.482 57.4798 327.55 56.3388 325.4 54.0964C323.37 51.9667 322.11 48.842 321.765 45.0471H354.923L354.969 44.7353C355.978 36.9334 354.538 30.2659 350.79 25.456L350.783 25.4493ZM333.647 26.3914C337.163 26.3914 340.082 27.5193 342.092 29.6555C343.923 31.6193 344.912 34.2929 344.945 37.4044H322.043C322.508 34.0474 323.801 31.2809 325.765 29.3702C327.782 27.4197 330.509 26.3848 333.647 26.3848V26.3914Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M311.315 19.3657L311.143 19.8699L295.406 64.6715H282.681L282.595 64.426L266.772 19.3657H277.639L277.726 19.6178L289.044 53.4064L300.455 19.3657H311.315Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M265.2 55.7947V36.3628C265.2 30.2327 263.475 25.5621 260.065 22.4705C256.828 19.5315 252.097 18.0387 245.987 18.0387C240.189 18.0387 235.545 19.3988 232.201 22.079C228.844 24.7593 226.84 28.72 226.263 33.8483L226.21 34.2597H236.155L236.202 33.9346C236.493 31.5794 237.449 29.755 239.048 28.5077C240.686 27.214 243.002 26.5639 245.908 26.5639C248.634 26.5639 250.877 27.1477 252.396 28.2556C254.068 29.4697 254.917 31.3074 254.917 33.7024C254.917 34.943 254.665 35.7856 254.181 36.3163C253.776 36.7277 253.205 36.9798 252.356 37.0992L241.111 37.9351C235.989 38.2801 231.982 39.7065 229.229 42.1346C226.502 44.5363 225.129 47.8004 225.129 51.8274C225.129 55.8544 226.595 59.4768 229.375 62.0177C232.228 64.6117 236.268 65.9917 241.051 65.9917C248.117 65.9917 253.557 63.0261 256.443 57.6324C256.702 59.7023 257.411 61.3476 258.539 62.5153C259.919 63.935 261.916 64.6648 264.49 64.6648H268.842V55.7881H265.22L265.2 55.7947ZM242.716 57.5661C240.381 57.5661 238.57 57.0353 237.323 55.9937C236.042 54.9322 235.392 53.3533 235.392 51.3032C235.392 49.4257 235.943 48.0259 237.084 47.0042C238.311 45.9096 240.275 45.2461 242.922 45.0404L243.061 45.0272L255.076 44.178V45.4717C255.076 48.9879 253.862 52.0065 251.58 54.2224C249.344 56.3852 246.199 57.5661 242.71 57.5661H242.716Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M216.79 25.4493C213.022 20.6063 207.216 18.0454 199.998 18.0454C193.211 18.0454 187.506 20.3343 183.499 24.6665C179.538 28.9324 177.442 34.9364 177.442 42.0219C177.442 49.1073 179.558 55.191 183.572 59.4569C187.599 63.736 193.311 66.005 200.078 66.005C210.64 66.005 218.468 60.3724 220.518 51.3099L220.618 50.8522H210.514L210.441 51.1109C209.538 54.0499 206.294 57.4798 200.085 57.4798C196.482 57.4798 193.55 56.3388 191.4 54.0964C189.37 51.9667 188.11 48.842 187.765 45.0471H220.923L220.969 44.7353C221.991 36.9334 220.545 30.2659 216.79 25.456V25.4493ZM188.043 37.411C188.508 34.054 189.801 31.2875 191.765 29.3768C193.782 27.4264 196.509 26.3914 199.647 26.3914C203.163 26.3914 206.082 27.5193 208.092 29.6555C209.93 31.6193 210.912 34.2929 210.945 37.4044H188.043V37.411Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M176.5 19.3657L176.347 19.8433L162.833 64.6715H152.019L151.946 64.4061L143.806 34.6378L135.513 64.6715H124.785L124.713 64.4127L111.119 19.3657H121.813L121.886 19.6376L130.192 50.9517L138.93 19.3657H148.689L148.762 19.6376L157.34 50.9517L165.806 19.3657H176.5Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M107.291 19.3657V28.2424H92.6157V64.6715H82.4121V29.6356C82.4121 26.3383 83.3144 23.7775 85.0791 22.0061C86.8372 20.2613 89.3981 19.3657 92.6755 19.3657H107.284H107.291Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M76.6923 6.03726C76.6923 9.48047 74.0452 11.975 70.3963 11.975C66.7474 11.975 64.1003 9.48047 64.1003 6.03726C64.1003 2.59404 66.8668 1.57356e-05 70.3963 1.57356e-05C73.9258 1.57356e-05 76.6923 2.64712 76.6923 6.03726Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M75.4521 19.3657H65.2485V64.6715H75.4521V19.3657Z",
                      fill: "currentColor"
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    "path",
                    {
                      d: "M38.4857 7.50345C37.1854 4.17965 34.0341 2.04339 30.4648 2.04339C26.8956 2.04339 23.7575 4.17965 22.4572 7.50345L0 64.6714H11.4973L18.0454 47.6942H42.9108L49.3594 64.4326L49.4589 64.6714H60.9562L38.499 7.50345H38.4857ZM21.2365 38.3862L30.4184 14.3899L39.6136 38.3862H21.2365Z",
                      fill: "currentColor"
                    }
                  )
                ]
              }
            ) })
          ] })
        }
      ) }) }),
      /* @__PURE__ */ jsx(SidebarMenu, { children: /* @__PURE__ */ jsx(SidebarMenuItem, { children: /* @__PURE__ */ jsxs(
        Button,
        {
          className: "w-full justify-start gap-2 bg-slate-50 text-slate-900 group-data-[collapsible=icon]:pl-2 hover:bg-slate-200",
          size: "sm",
          onClick: openCreateCollection,
          children: [
            /* @__PURE__ */ jsx(Plus, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { className: "group-data-[collapsible=icon]:hidden", children: "Create Collection" })
          ]
        }
      ) }) })
    ] }),
    /* @__PURE__ */ jsx(SidebarContent, { children: /* @__PURE__ */ jsx(SidebarGroup, { children: /* @__PURE__ */ jsx(SidebarGroupContent, { children: /* @__PURE__ */ jsx(SidebarMenu, { children: navItems.map((item) => /* @__PURE__ */ jsx(SidebarMenuItem, { children: /* @__PURE__ */ jsx(
      SidebarMenuButton,
      {
        asChild: true,
        isActive: isActive(item.to),
        tooltip: item.title,
        children: /* @__PURE__ */ jsxs(Link, { to: item.to, params: { orgSlug }, children: [
          /* @__PURE__ */ jsx(item.icon, {}),
          /* @__PURE__ */ jsx("span", { children: item.title })
        ] })
      }
    ) }, item.title)) }) }) }) }),
    /* @__PURE__ */ jsx(SidebarFooter, { children: /* @__PURE__ */ jsx(SidebarMenu, { children: /* @__PURE__ */ jsx(SidebarMenuItem, { children: /* @__PURE__ */ jsx(UserAccountDropdown, { variant: "sidebar" }) }) }) }),
    /* @__PURE__ */ jsx(SidebarRail, {})
  ] });
}
function Dialog({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Root, { "data-slot": "dialog", ...props });
}
function DialogTrigger({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Trigger, { "data-slot": "dialog-trigger", ...props });
}
function DialogPortal({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Portal, { "data-slot": "dialog-portal", ...props });
}
function DialogClose({
  ...props
}) {
  return /* @__PURE__ */ jsx(SheetPrimitive.Close, { "data-slot": "dialog-close", ...props });
}
function DialogOverlay({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SheetPrimitive.Overlay,
    {
      "data-slot": "dialog-overlay",
      className: cn(
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50",
        className
      ),
      ...props
    }
  );
}
function DialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}) {
  return /* @__PURE__ */ jsxs(DialogPortal, { children: [
    /* @__PURE__ */ jsx(DialogOverlay, {}),
    /* @__PURE__ */ jsxs(
      SheetPrimitive.Content,
      {
        "data-slot": "dialog-content",
        className: cn(
          "bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 sm:max-w-lg",
          className
        ),
        ...props,
        children: [
          children,
          showCloseButton && /* @__PURE__ */ jsxs(SheetPrimitive.Close, { className: "ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:pointer-events-none", children: [
            /* @__PURE__ */ jsx(X$1, { className: "h-4 w-4" }),
            /* @__PURE__ */ jsx("span", { className: "sr-only", children: "Close" })
          ] })
        ]
      }
    )
  ] });
}
function DialogHeader({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "dialog-header",
      className: cn("flex flex-col gap-2 text-center sm:text-left", className),
      ...props
    }
  );
}
function DialogFooter({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "dialog-footer",
      className: cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className
      ),
      ...props
    }
  );
}
function DialogTitle({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SheetPrimitive.Title,
    {
      "data-slot": "dialog-title",
      className: cn("text-lg font-semibold", className),
      ...props
    }
  );
}
function DialogDescription({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SheetPrimitive.Description,
    {
      "data-slot": "dialog-description",
      className: cn("text-muted-foreground text-sm", className),
      ...props
    }
  );
}
function Command({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    Command$1,
    {
      "data-slot": "command",
      className: cn(
        "bg-popover text-popover-foreground flex h-full w-full flex-col overflow-hidden rounded-md",
        className
      ),
      ...props
    }
  );
}
function CommandDialog({
  title = "Command Palette",
  description = "Search for a command to run...",
  children,
  className,
  showCloseButton = true,
  ...props
}) {
  return /* @__PURE__ */ jsxs(Dialog, { ...props, children: [
    /* @__PURE__ */ jsxs(DialogHeader, { className: "sr-only", children: [
      /* @__PURE__ */ jsx(DialogTitle, { children: title }),
      /* @__PURE__ */ jsx(DialogDescription, { children: description })
    ] }),
    /* @__PURE__ */ jsx(
      DialogContent,
      {
        className: cn("overflow-hidden p-0", className),
        showCloseButton,
        children: /* @__PURE__ */ jsx(Command, { className: "[&_[cmdk-group-heading]]:text-muted-foreground **:data-[slot=command-input-wrapper]:h-12 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group]]:px-2 [&_[cmdk-group]:not([hidden])_~[cmdk-group]]:pt-0 [&_[cmdk-input-wrapper]_svg]:h-5 [&_[cmdk-input-wrapper]_svg]:w-5 [&_[cmdk-input]]:h-12 [&_[cmdk-item]]:px-2 [&_[cmdk-item]]:py-3 [&_[cmdk-item]_svg]:h-5 [&_[cmdk-item]_svg]:w-5", children })
      }
    )
  ] });
}
function CommandInput({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsxs(
    "div",
    {
      "data-slot": "command-input-wrapper",
      className: "flex h-9 items-center gap-2 border-b px-3",
      children: [
        /* @__PURE__ */ jsx(Search, { className: "size-4 shrink-0 opacity-50" }),
        /* @__PURE__ */ jsx(
          Command$1.Input,
          {
            "data-slot": "command-input",
            className: cn(
              "placeholder:text-muted-foreground flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-hidden disabled:cursor-not-allowed disabled:opacity-50",
              className
            ),
            ...props
          }
        )
      ]
    }
  );
}
function CommandList({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    Command$1.List,
    {
      "data-slot": "command-list",
      className: cn(
        "max-h-[300px] scroll-py-1 overflow-x-hidden overflow-y-auto",
        className
      ),
      ...props
    }
  );
}
function CommandEmpty({
  ...props
}) {
  return /* @__PURE__ */ jsx(
    Command$1.Empty,
    {
      "data-slot": "command-empty",
      className: "py-6 text-center text-sm",
      ...props
    }
  );
}
function CommandGroup({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    Command$1.Group,
    {
      "data-slot": "command-group",
      className: cn(
        "text-foreground [&_[cmdk-group-heading]]:text-muted-foreground overflow-hidden p-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium",
        className
      ),
      ...props
    }
  );
}
function CommandSeparator({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    Command$1.Separator,
    {
      "data-slot": "command-separator",
      className: cn("bg-border -mx-1 h-px", className),
      ...props
    }
  );
}
function CommandItem({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    Command$1.Item,
    {
      "data-slot": "command-item",
      className: cn(
        "data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground [&_svg:not([class*='text-'])]:text-muted-foreground relative flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className
      ),
      ...props
    }
  );
}
function CommandShortcut({
  className,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    "span",
    {
      "data-slot": "command-shortcut",
      className: cn(
        "text-muted-foreground ml-auto text-xs tracking-widest",
        className
      ),
      ...props
    }
  );
}
const useCommandStore = create((set2) => ({
  open: false,
  setOpen: (open) => set2({ open }),
  toggle: () => set2((state) => ({ open: !state.open })),
  pageTitle: null,
  pageCommands: [],
  setPageCommands: (title, commands) => set2({ pageTitle: title, pageCommands: commands }),
  clearPageCommands: () => set2({ pageTitle: null, pageCommands: [] }),
  contextTitle: null,
  contextCommands: [],
  setContextCommands: (title, commands) => set2({ contextTitle: title, contextCommands: commands }),
  clearContextCommands: () => set2({ contextTitle: null, contextCommands: [] })
}));
function useCommandMenu({
  pageTitle,
  pageCommands = [],
  contextTitle,
  contextCommands = []
} = {}) {
  const setPageCommands = useCommandStore((state) => state.setPageCommands);
  const clearPageCommands = useCommandStore((state) => state.clearPageCommands);
  const setContextCommands = useCommandStore(
    (state) => state.setContextCommands
  );
  const clearContextCommands = useCommandStore(
    (state) => state.clearContextCommands
  );
  const pageCommandIds = useMemo(
    () => pageCommands.map((c2) => c2.id).join(","),
    [pageCommands]
  );
  const contextCommandIds = useMemo(
    () => contextCommands.map((c2) => c2.id).join(","),
    [contextCommands]
  );
  useEffect(() => {
    setPageCommands(pageTitle ?? null, pageCommands);
    return () => clearPageCommands();
  }, [
    pageTitle,
    pageCommandIds,
    pageCommands,
    setPageCommands,
    clearPageCommands
  ]);
  useEffect(() => {
    setContextCommands(contextTitle ?? null, contextCommands);
    return () => clearContextCommands();
  }, [
    contextTitle,
    contextCommandIds,
    contextCommands,
    setContextCommands,
    clearContextCommands
  ]);
}
function useCommandMenuOpen() {
  const open = useCommandStore((state) => state.open);
  const setOpen = useCommandStore((state) => state.setOpen);
  const toggle = useCommandStore((state) => state.toggle);
  return { open, setOpen, toggle };
}
function CommandMenu() {
  const { open, setOpen } = useCommandMenuOpen();
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const orgSlug = params.orgSlug;
  const setTheme = useUISettings((state) => state.setTheme);
  const toggleLeftSidebar = useUISettings((state) => state.toggleLeftSidebar);
  const toggleRightSidebarTab = useUISettings(
    (state) => state.toggleRightSidebarTab
  );
  const pageTitle = useCommandStore((state) => state.pageTitle);
  const pageCommands = useCommandStore((state) => state.pageCommands);
  const contextTitle = useCommandStore((state) => state.contextTitle);
  const contextCommands = useCommandStore((state) => state.contextCommands);
  useEffect(() => {
    const down = (e2) => {
      if (e2.key === "k" && (e2.metaKey || e2.ctrlKey)) {
        e2.preventDefault();
        setOpen(!open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, setOpen]);
  const runCommand = (callback) => {
    setOpen(false);
    callback();
  };
  return /* @__PURE__ */ jsxs(CommandDialog, { open, onOpenChange: setOpen, showCloseButton: false, children: [
    /* @__PURE__ */ jsx(CommandInput, { placeholder: "Type a command or search..." }),
    /* @__PURE__ */ jsxs(CommandList, { children: [
      /* @__PURE__ */ jsx(CommandEmpty, { children: "No results found." }),
      contextCommands.length > 0 && /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx(CommandGroup, { heading: contextTitle ?? "Actions", children: contextCommands.map((command) => /* @__PURE__ */ jsxs(
          CommandItem,
          {
            value: command.label,
            keywords: command.keywords,
            onSelect: () => runCommand(command.onSelect),
            children: [
              command.icon && /* @__PURE__ */ jsx(command.icon, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { children: command.label }),
              command.shortcut && /* @__PURE__ */ jsx(CommandShortcut, { children: command.shortcut })
            ]
          },
          command.id
        )) }),
        /* @__PURE__ */ jsx(CommandSeparator, {})
      ] }),
      pageCommands.length > 0 && /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx(CommandGroup, { heading: pageTitle ?? "Actions", children: pageCommands.map((command) => /* @__PURE__ */ jsxs(
          CommandItem,
          {
            value: command.label,
            keywords: command.keywords,
            onSelect: () => runCommand(command.onSelect),
            children: [
              command.icon && /* @__PURE__ */ jsx(command.icon, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { children: command.label }),
              command.shortcut && /* @__PURE__ */ jsx(CommandShortcut, { children: command.shortcut })
            ]
          },
          command.id
        )) }),
        /* @__PURE__ */ jsx(CommandSeparator, {})
      ] }),
      orgSlug && /* @__PURE__ */ jsx(CommandGroup, { heading: "Navigation", children: navItems.map((item) => /* @__PURE__ */ jsxs(
        CommandItem,
        {
          value: item.title,
          onSelect: () => runCommand(
            () => navigate({ to: item.to, params: { orgSlug } })
          ),
          children: [
            /* @__PURE__ */ jsx(item.icon, { className: "size-4" }),
            /* @__PURE__ */ jsxs("span", { children: [
              "Go to ",
              item.title
            ] })
          ]
        },
        item.to
      )) }),
      /* @__PURE__ */ jsx(CommandSeparator, {}),
      /* @__PURE__ */ jsxs(CommandGroup, { heading: "View", children: [
        /* @__PURE__ */ jsxs(
          CommandItem,
          {
            value: "Toggle Sidebar",
            keywords: ["collapse", "expand", "navigation", "menu"],
            onSelect: () => runCommand(toggleLeftSidebar),
            children: [
              /* @__PURE__ */ jsx(PanelLeft, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { children: "Toggle Sidebar" }),
              /* @__PURE__ */ jsx(CommandShortcut, { children: "⌘B" })
            ]
          }
        ),
        /* @__PURE__ */ jsxs(
          CommandItem,
          {
            value: "Open Documentation",
            keywords: ["docs", "help", "guide", "panel"],
            onSelect: () => runCommand(() => toggleRightSidebarTab("docs")),
            children: [
              /* @__PURE__ */ jsx(BookOpen, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { children: "Open Documentation" })
            ]
          }
        ),
        /* @__PURE__ */ jsxs(
          CommandItem,
          {
            value: "Open Code",
            keywords: ["snippet", "example", "panel"],
            onSelect: () => runCommand(() => toggleRightSidebarTab("code")),
            children: [
              /* @__PURE__ */ jsx(CodeXml, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { children: "Open Code" })
            ]
          }
        ),
        /* @__PURE__ */ jsxs(
          CommandItem,
          {
            value: "Open Help",
            keywords: ["support", "faq", "panel"],
            onSelect: () => runCommand(() => toggleRightSidebarTab("help")),
            children: [
              /* @__PURE__ */ jsx(CircleQuestionMark, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { children: "Open Help" })
            ]
          }
        )
      ] }),
      /* @__PURE__ */ jsx(CommandSeparator, {}),
      /* @__PURE__ */ jsx(CommandGroup, { heading: "Theme", children: themeOptions.map((option) => /* @__PURE__ */ jsxs(
        CommandItem,
        {
          value: option.label,
          onSelect: () => runCommand(() => setTheme(option.value)),
          children: [
            /* @__PURE__ */ jsx(option.icon, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { children: option.label })
          ]
        },
        option.value
      )) })
    ] })
  ] });
}
const PageHeaderContext = React.createContext(
  null
);
function usePageHeaderContext() {
  const context = React.useContext(PageHeaderContext);
  if (!context) {
    throw new Error(
      "usePageHeaderContext must be used within a PageHeaderProvider."
    );
  }
  return context;
}
function usePageHeader(content) {
  const { setContent } = usePageHeaderContext();
  const contentRef = React.useRef(content);
  React.useLayoutEffect(() => {
    contentRef.current = content;
  });
  React.useEffect(() => {
    setContent(contentRef.current);
    return () => {
      setContent({});
    };
  }, [setContent]);
}
function PageHeaderProvider({ children }) {
  const [content, setContent] = React.useState({});
  const contextValue = React.useMemo(
    () => ({
      content,
      setContent
    }),
    [content]
  );
  return /* @__PURE__ */ jsx(PageHeaderContext.Provider, { value: contextValue, children });
}
function PageHeaderContent() {
  const { content } = usePageHeaderContext();
  if (!content.title) {
    return null;
  }
  return /* @__PURE__ */ jsxs("div", { className: "flex flex-1 items-center justify-between gap-4", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex min-w-0 items-center gap-2", children: [
      /* @__PURE__ */ jsx("h1", { className: "truncate font-mono text-sm font-medium uppercase", children: content.title }),
      content.description && /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs(
          "button",
          {
            type: "button",
            className: "text-muted-foreground hover:text-foreground inline-flex items-center justify-center transition-colors",
            children: [
              /* @__PURE__ */ jsx(CircleQuestionMark, { className: "size-4" }),
              /* @__PURE__ */ jsx("span", { className: "sr-only", children: "More info" })
            ]
          }
        ) }),
        /* @__PURE__ */ jsx(TooltipContent, { side: "bottom", className: "max-w-xs", children: content.description })
      ] })
    ] }),
    content.actions && /* @__PURE__ */ jsx("div", { className: "flex shrink-0 items-center gap-2", children: content.actions })
  ] });
}
const Toaster = ({ ...props }) => {
  const theme = useUISettings((state) => state.theme);
  const resolvedTheme = theme === "system" ? window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light" : theme;
  return /* @__PURE__ */ jsx(
    Toaster$1,
    {
      theme: resolvedTheme,
      className: "toaster group",
      icons: {
        success: /* @__PURE__ */ jsx(CircleCheck, { className: "size-4" }),
        info: /* @__PURE__ */ jsx(Info, { className: "size-4" }),
        warning: /* @__PURE__ */ jsx(TriangleAlert, { className: "size-4" }),
        error: /* @__PURE__ */ jsx(OctagonX, { className: "size-4" }),
        loading: /* @__PURE__ */ jsx(LoaderCircle, { className: "size-4 animate-spin" })
      },
      style: {
        "--normal-bg": "var(--popover)",
        "--normal-text": "var(--popover-foreground)",
        "--normal-border": "var(--border)",
        "--border-radius": "var(--radius)"
      },
      ...props
    }
  );
};
function useThemeEffect() {
  const theme = useUISettings((state) => state.theme);
  useEffect(() => {
    const root = document.documentElement;
    const applyTheme = (isDark) => {
      if (isDark) {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    };
    if (theme === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      applyTheme(mediaQuery.matches);
      const handleChange = (e2) => {
        applyTheme(e2.matches);
      };
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    } else {
      applyTheme(theme === "dark");
    }
  }, [theme]);
}
const IDB_KEY = "airweave-query-cache";
function createIDBPersister() {
  return {
    persistClient: async (client) => {
      try {
        await set(IDB_KEY, client);
      } catch (error) {
        console.debug("Failed to persist query cache:", error);
      }
    },
    restoreClient: async () => {
      try {
        const client = await get(IDB_KEY);
        if (!client) return void 0;
        return {
          ...client,
          clientState: {
            ...client.clientState,
            queries: client.clientState.queries.map((query) => ({
              ...query,
              state: {
                ...query.state,
                dataUpdatedAt: 0
              }
            }))
          }
        };
      } catch (error) {
        console.debug("Failed to restore query cache:", error);
        return void 0;
      }
    },
    removeClient: async () => {
      try {
        await del(IDB_KEY);
      } catch (error) {
        console.debug("Failed to remove query cache:", error);
      }
    }
  };
}
const CACHE_MAX_AGE = 1e3 * 60 * 60;
const appCss = "/assets/styles-D-7nFG_c.css";
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Matches IndexedDB persistence duration
      gcTime: CACHE_MAX_AGE
    }
  }
});
const persister = createIDBPersister();
const Route$d = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: "utf-8"
      },
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1"
      },
      {
        title: "Airweave"
      }
    ],
    links: [
      {
        rel: "preconnect",
        href: "https://fonts.googleapis.com"
      },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous"
      },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Fira+Code:wght@300..700&display=swap"
      },
      {
        rel: "stylesheet",
        href: appCss
      }
    ]
  }),
  component: RootComponent,
  shellComponent: RootDocument
});
function RootComponent() {
  const isHydrated = useUISettingsHydrated();
  const isMobile = useIsMobile();
  const params = useParams({ strict: false });
  const hasOrgContext = Boolean(params.orgSlug);
  useThemeEffect();
  if (!isHydrated) {
    return null;
  }
  if (!hasOrgContext) {
    return /* @__PURE__ */ jsxs(AuthGuard, { children: [
      /* @__PURE__ */ jsx(Outlet, {}),
      /* @__PURE__ */ jsx(Toaster, {})
    ] });
  }
  return /* @__PURE__ */ jsxs(AuthGuard, { children: [
    /* @__PURE__ */ jsx(CommandMenu, {}),
    /* @__PURE__ */ jsx(PageHeaderProvider, { children: /* @__PURE__ */ jsx(SidebarProvider, { children: /* @__PURE__ */ jsxs(RightSidebarProvider, { children: [
      /* @__PURE__ */ jsx(AppSidebar, {}),
      /* @__PURE__ */ jsx(SidebarInset, { children: /* @__PURE__ */ jsx(
        "div",
        {
          className: cn(
            "bg-sidebar h-full px-1",
            isMobile ? "p-0" : "py-4"
          ),
          children: /* @__PURE__ */ jsxs(
            "div",
            {
              className: cn(
                "bg-background border-border/50 flex h-full flex-col border shadow-sm",
                isMobile ? "rounded-none" : "rounded-lg"
              ),
              children: [
                /* @__PURE__ */ jsxs("header", { className: "flex h-14 shrink-0 items-center border-b px-4", children: [
                  /* @__PURE__ */ jsx(SidebarTrigger, { className: "mr-1.5 -ml-1" }),
                  /* @__PURE__ */ jsx(PageHeaderContent, {})
                ] }),
                /* @__PURE__ */ jsx("div", { className: "flex-1 overflow-auto pb-16 md:pb-0", children: /* @__PURE__ */ jsx(Outlet, {}) })
              ]
            }
          )
        }
      ) }),
      /* @__PURE__ */ jsx(AppRightSidebar, {})
    ] }) }) }),
    /* @__PURE__ */ jsx(Toaster, {})
  ] });
}
function RootDocument({ children }) {
  return /* @__PURE__ */ jsxs("html", { lang: "en", children: [
    /* @__PURE__ */ jsx("head", { children: /* @__PURE__ */ jsx(HeadContent, {}) }),
    /* @__PURE__ */ jsxs("body", { children: [
      /* @__PURE__ */ jsx(
        PersistQueryClientProvider,
        {
          client: queryClient,
          persistOptions: {
            persister,
            maxAge: CACHE_MAX_AGE
          },
          children: /* @__PURE__ */ jsx(AuthProvider, { children })
        }
      ),
      /* @__PURE__ */ jsx(Scripts, {})
    ] })
  ] });
}
const $$splitComponentImporter$b = () => import("./onboarding-CktMhaUJ.mjs");
const Route$c = createFileRoute("/onboarding")({
  component: lazyRouteComponent($$splitComponentImporter$b, "component")
});
const $$splitComponentImporter$a = () => import("./components-ZgYMixR7.mjs");
const Route$b = createFileRoute("/components")({
  component: lazyRouteComponent($$splitComponentImporter$a, "component")
});
const $$splitComponentImporter$9 = () => import("./route-CJ3Bli3o.mjs");
const Route$a = createFileRoute("/$orgSlug")({
  component: lazyRouteComponent($$splitComponentImporter$9, "component")
});
const $$splitComponentImporter$8 = () => import("./index-CJEWmIzU.mjs");
const Route$9 = createFileRoute("/")({
  component: lazyRouteComponent($$splitComponentImporter$8, "component")
});
const $$splitComponentImporter$7 = () => import("./components.index-DzwwNVC4.mjs");
const Route$8 = createFileRoute("/components/")({
  component: lazyRouteComponent($$splitComponentImporter$7, "component")
});
const Route$7 = createFileRoute("/$orgSlug/")({
  beforeLoad: ({ params }) => {
    throw redirect({
      to: "/$orgSlug/collections",
      params: { orgSlug: params.orgSlug }
    });
  }
});
const $$splitComponentImporter$6 = () => import("./components._componentName-CGduDfNO.mjs");
const Route$6 = createFileRoute("/components/$componentName")({
  component: lazyRouteComponent($$splitComponentImporter$6, "component")
});
const $$splitComponentImporter$5 = () => import("./webhooks-DgmA8Z1L.mjs");
const Route$5 = createFileRoute("/$orgSlug/webhooks")({
  component: lazyRouteComponent($$splitComponentImporter$5, "component")
});
const $$splitComponentImporter$4 = () => import("./logs-BUSqK4hq.mjs");
const Route$4 = createFileRoute("/$orgSlug/logs")({
  component: lazyRouteComponent($$splitComponentImporter$4, "component")
});
const $$splitComponentImporter$3 = () => import("./auth-providers-Cweauae-.mjs");
const Route$3 = createFileRoute("/$orgSlug/auth-providers")({
  component: lazyRouteComponent($$splitComponentImporter$3, "component")
});
const $$splitComponentImporter$2 = () => import("./api-keys-Bd1-pD9E.mjs");
const Route$2 = createFileRoute("/$orgSlug/api-keys")({
  component: lazyRouteComponent($$splitComponentImporter$2, "component")
});
const $$splitComponentImporter$1 = () => import("./index-xMN8dMLC.mjs");
const Route$1 = createFileRoute("/$orgSlug/collections/")({
  component: lazyRouteComponent($$splitComponentImporter$1, "component")
});
const $$splitComponentImporter = () => import("./_collectionId-DE9RRwxs.mjs");
const Route = createFileRoute("/$orgSlug/collections/$collectionId")({
  component: lazyRouteComponent($$splitComponentImporter, "component")
});
const OnboardingRoute = Route$c.update({
  id: "/onboarding",
  path: "/onboarding",
  getParentRoute: () => Route$d
});
const ComponentsRoute = Route$b.update({
  id: "/components",
  path: "/components",
  getParentRoute: () => Route$d
});
const OrgSlugRouteRoute = Route$a.update({
  id: "/$orgSlug",
  path: "/$orgSlug",
  getParentRoute: () => Route$d
});
const IndexRoute = Route$9.update({
  id: "/",
  path: "/",
  getParentRoute: () => Route$d
});
const ComponentsIndexRoute = Route$8.update({
  id: "/",
  path: "/",
  getParentRoute: () => ComponentsRoute
});
const OrgSlugIndexRoute = Route$7.update({
  id: "/",
  path: "/",
  getParentRoute: () => OrgSlugRouteRoute
});
const ComponentsComponentNameRoute = Route$6.update({
  id: "/$componentName",
  path: "/$componentName",
  getParentRoute: () => ComponentsRoute
});
const OrgSlugWebhooksRoute = Route$5.update({
  id: "/webhooks",
  path: "/webhooks",
  getParentRoute: () => OrgSlugRouteRoute
});
const OrgSlugLogsRoute = Route$4.update({
  id: "/logs",
  path: "/logs",
  getParentRoute: () => OrgSlugRouteRoute
});
const OrgSlugAuthProvidersRoute = Route$3.update({
  id: "/auth-providers",
  path: "/auth-providers",
  getParentRoute: () => OrgSlugRouteRoute
});
const OrgSlugApiKeysRoute = Route$2.update({
  id: "/api-keys",
  path: "/api-keys",
  getParentRoute: () => OrgSlugRouteRoute
});
const OrgSlugCollectionsIndexRoute = Route$1.update({
  id: "/collections/",
  path: "/collections/",
  getParentRoute: () => OrgSlugRouteRoute
});
const OrgSlugCollectionsCollectionIdRoute = Route.update({
  id: "/collections/$collectionId",
  path: "/collections/$collectionId",
  getParentRoute: () => OrgSlugRouteRoute
});
const OrgSlugRouteRouteChildren = {
  OrgSlugApiKeysRoute,
  OrgSlugAuthProvidersRoute,
  OrgSlugLogsRoute,
  OrgSlugWebhooksRoute,
  OrgSlugIndexRoute,
  OrgSlugCollectionsCollectionIdRoute,
  OrgSlugCollectionsIndexRoute
};
const OrgSlugRouteRouteWithChildren = OrgSlugRouteRoute._addFileChildren(
  OrgSlugRouteRouteChildren
);
const ComponentsRouteChildren = {
  ComponentsComponentNameRoute,
  ComponentsIndexRoute
};
const ComponentsRouteWithChildren = ComponentsRoute._addFileChildren(
  ComponentsRouteChildren
);
const rootRouteChildren = {
  IndexRoute,
  OrgSlugRouteRoute: OrgSlugRouteRouteWithChildren,
  ComponentsRoute: ComponentsRouteWithChildren,
  OnboardingRoute
};
const routeTree = Route$d._addFileChildren(rootRouteChildren)._addFileTypes();
const getRouter = () => {
  const router2 = createRouter({
    routeTree,
    context: {},
    scrollRestoration: true,
    defaultPreloadStaleTime: 0
  });
  return router2;
};
const router = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  getRouter
}, Symbol.toStringTag, { value: "Module" }));
const routerBGxBdlkD = /* @__PURE__ */ Object.freeze({
  __proto__: null,
  $: Route$6,
  A: Avatar,
  B: Button,
  C: Command,
  D: Dialog,
  E: DropdownMenu,
  F: DropdownMenuTrigger,
  G: DropdownMenuContent,
  H: DropdownMenuLabel,
  I: DropdownMenuSeparator,
  J: DropdownMenuGroup,
  K: DropdownMenuItem,
  L: DropdownMenuShortcut,
  M: DropdownMenuSub,
  N: DropdownMenuSubTrigger,
  O: DropdownMenuSubContent,
  P: SheetTrigger,
  Q: SheetContent,
  R: SheetHeader,
  S: Sheet,
  T: SheetTitle,
  U: UserAccountDropdown,
  V: SheetDescription,
  W: SheetFooter,
  X: SheetClose,
  Y: Tooltip,
  Z: TooltipTrigger,
  _: TooltipContent,
  a: createOrganization,
  a0: usePageHeader,
  a1: useRightSidebarContent,
  a2: API_BASE_URL,
  a3: getAuthHeaders,
  a4: parseErrorResponse,
  a5: useCommandMenu,
  a6: TooltipProvider,
  a7: Route,
  a8: useUISettings,
  a9: findOrgBySlug,
  aa: buttonVariants,
  ab: router,
  b: authConfig,
  c: cn,
  d: createCheckoutSession,
  e: DialogContent,
  f: fetchOrganizations,
  g: generateOrgSlug,
  h: DialogHeader,
  i: DialogTitle,
  j: DialogDescription,
  k: useCreateCollectionStore,
  l: getPrimaryOrg,
  m: AvatarImage,
  n: AvatarFallback,
  o: CommandInput,
  p: CommandList,
  q: queryKeys,
  r: CommandEmpty,
  s: CommandGroup,
  t: CommandItem,
  u: useAuth0,
  v: CommandSeparator,
  w: CommandShortcut,
  x: DialogTrigger,
  y: DialogFooter,
  z: DialogClose
});
export {
  CommandInput as $,
  Search as A,
  Button as B,
  CodeXml as C,
  Dialog as D,
  DropdownMenu as E,
  DropdownMenuTrigger as F,
  DropdownMenuContent as G,
  DropdownMenuLabel as H,
  DropdownMenuSeparator as I,
  DropdownMenuGroup as J,
  DropdownMenuItem as K,
  LoaderCircle as L,
  DropdownMenuShortcut as M,
  DropdownMenuSub as N,
  DropdownMenuSubTrigger as O,
  Plus as P,
  DropdownMenuSubContent as Q,
  Route$6 as R,
  Sheet as S,
  Tooltip as T,
  UserAccountDropdown as U,
  LogOut as V,
  DialogTrigger as W,
  X$1 as X,
  DialogFooter as Y,
  DialogClose as Z,
  Command as _,
  cn as a,
  CommandList as a0,
  CommandEmpty as a1,
  CommandGroup as a2,
  CommandItem as a3,
  CommandSeparator as a4,
  CommandShortcut as a5,
  Avatar as a6,
  AvatarImage as a7,
  AvatarFallback as a8,
  usePageHeader as a9,
  useRightSidebarContent as aa,
  Webhook as ab,
  Terminal as ac,
  ShieldCheck as ad,
  TriangleAlert as ae,
  API_BASE_URL as af,
  getAuthHeaders as ag,
  parseErrorResponse as ah,
  useCommandMenu as ai,
  Key as aj,
  CircleCheck as ak,
  LayoutGrid as al,
  Route as am,
  TooltipProvider as an,
  Info as ao,
  CircleQuestionMark as ap,
  useUISettings as aq,
  findOrgBySlug as ar,
  buttonVariants as as,
  routerBGxBdlkD as at,
  authConfig as b,
  createLucideIcon as c,
  createOrganization as d,
  createCheckoutSession as e,
  fetchOrganizations as f,
  generateOrgSlug as g,
  Check as h,
  ChevronRight as i,
  useCreateCollectionStore as j,
  DialogContent as k,
  DialogHeader as l,
  DialogTitle as m,
  DialogDescription as n,
  getPrimaryOrg as o,
  TooltipTrigger as p,
  queryKeys as q,
  TooltipContent as r,
  SheetTrigger as s,
  SheetContent as t,
  useAuth0 as u,
  SheetHeader as v,
  SheetTitle as w,
  SheetDescription as x,
  SheetFooter as y,
  SheetClose as z
};
