import { jsx, Fragment, jsxs } from "react/jsx-runtime";
import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import React__default from "react";
import { c as createLucideIcon, a as cn, ao as Info, ae as TriangleAlert } from "./router-BGxBdlkD.mjs";
const __iconNode$1 = [["path", { d: "m6 9 6 6 6-6", key: "qrunsl" }]];
const ChevronDown = createLucideIcon("chevron-down", __iconNode$1);
const __iconNode = [
  [
    "path",
    {
      d: "M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5",
      key: "1gvzjb"
    }
  ],
  ["path", { d: "M9 18h6", key: "x1upvd" }],
  ["path", { d: "M10 22h4", key: "ceow96" }]
];
const Lightbulb = createLucideIcon("lightbulb", __iconNode);
function formatDate(dateString, style = "short") {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return dateString;
    }
    const options = style === "datetime" ? {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit"
    } : style === "long" ? {
      year: "numeric",
      month: "long",
      day: "numeric"
    } : {
      month: "short",
      day: "numeric",
      year: "numeric"
    };
    return date.toLocaleDateString("en-US", options);
  } catch {
    return dateString;
  }
}
function getDaysFromNow(dateString) {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return 0;
    }
    const now = /* @__PURE__ */ new Date();
    const diffTime = date.getTime() - now.getTime();
    return Math.ceil(diffTime / (1e3 * 60 * 60 * 24));
  } catch {
    return 0;
  }
}
const DOCS_BASE_URL = "https://docs.airweave.ai";
function Card({
  title,
  href,
  children
}) {
  const content = /* @__PURE__ */ jsxs("div", { className: "h-full rounded-lg border border-slate-700 bg-slate-800 p-4 transition-colors hover:bg-slate-700/50", children: [
    /* @__PURE__ */ jsx("h4", { className: "mb-1 text-sm font-semibold", children: title }),
    children && /* @__PURE__ */ jsx("div", { className: "text-xs text-slate-400", children })
  ] });
  if (href) {
    const finalHref = href.startsWith("http") ? href : `${DOCS_BASE_URL}${href}`;
    return /* @__PURE__ */ jsx(
      "a",
      {
        href: finalHref,
        target: "_blank",
        rel: "noopener noreferrer",
        className: "block no-underline",
        children: content
      }
    );
  }
  return content;
}
function CardGroup({
  cols = 2,
  children
}) {
  const gridCols = {
    1: "grid-cols-1",
    2: "grid-cols-1 sm:grid-cols-2",
    3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
  }[cols] || "grid-cols-1 sm:grid-cols-2";
  return /* @__PURE__ */ jsx("div", { className: cn("my-4 grid gap-3", gridCols), children });
}
function Steps({ children }) {
  return /* @__PURE__ */ jsx("div", { className: "my-4 space-y-4", children });
}
function Step({
  title,
  children
}) {
  return /* @__PURE__ */ jsxs("div", { className: "border-l-2 border-slate-500 py-2 pl-4", children: [
    /* @__PURE__ */ jsx("h4", { className: "mb-2 text-sm font-semibold", children: title }),
    /* @__PURE__ */ jsx("div", { className: "text-sm text-slate-400", children })
  ] });
}
function CodeBlocks({ children }) {
  const [activeTab, setActiveTab] = React.useState(0);
  const blocks = React.Children.toArray(children).filter(
    (child) => React.isValidElement(child) && child.type === "pre"
  );
  if (blocks.length === 0) {
    return /* @__PURE__ */ jsx("div", { className: "space-y-2", children });
  }
  const tabs = blocks.map((block, index) => {
    if (React.isValidElement(block)) {
      const blockProps = block.props;
      const codeElement = blockProps.children;
      if (React.isValidElement(codeElement)) {
        const title = codeElement.props.title || `Tab ${index + 1}`;
        return title;
      }
    }
    return `Tab ${index + 1}`;
  });
  return /* @__PURE__ */ jsxs("div", { className: "my-3", children: [
    /* @__PURE__ */ jsx("div", { className: "flex gap-1 border-b border-slate-700", children: tabs.map((tab, index) => /* @__PURE__ */ jsx(
      "button",
      {
        onClick: () => setActiveTab(index),
        className: cn(
          "px-3 py-1 text-xs font-medium transition-colors",
          activeTab === index ? "border-b-2 border-slate-500 text-slate-300" : "text-slate-400 hover:text-slate-100"
        ),
        children: tab
      },
      index
    )) }),
    /* @__PURE__ */ jsx("div", { className: "mt-2", children: blocks[activeTab] })
  ] });
}
const CodeGroup = CodeBlocks;
function CodeBlock({
  children
}) {
  return /* @__PURE__ */ jsx("div", { className: "my-3", children });
}
function Warning({ children }) {
  return /* @__PURE__ */ jsx("div", { className: "my-4 rounded-lg border border-amber-500/50 bg-amber-500/10 p-4", children: /* @__PURE__ */ jsxs("div", { className: "flex gap-3", children: [
    /* @__PURE__ */ jsx(TriangleAlert, { className: "mt-0.5 size-5 shrink-0 text-amber-500" }),
    /* @__PURE__ */ jsx("div", { className: "text-sm text-amber-900 dark:text-amber-100 [&>p]:mb-2 [&>p:last-child]:mb-0", children })
  ] }) });
}
function Note({ children }) {
  return /* @__PURE__ */ jsx("div", { className: "my-4 rounded-lg border border-blue-500/50 bg-blue-500/10 p-4", children: /* @__PURE__ */ jsxs("div", { className: "flex gap-3", children: [
    /* @__PURE__ */ jsx(Info, { className: "mt-0.5 size-5 shrink-0 text-blue-500" }),
    /* @__PURE__ */ jsx("div", { className: "text-sm text-blue-900 dark:text-blue-100 [&>p]:mb-2 [&>p:last-child]:mb-0", children })
  ] }) });
}
function Tip({ children }) {
  return /* @__PURE__ */ jsx("div", { className: "my-4 rounded-lg border border-green-500/50 bg-green-500/10 p-4", children: /* @__PURE__ */ jsxs("div", { className: "flex gap-3", children: [
    /* @__PURE__ */ jsx(Lightbulb, { className: "mt-0.5 size-5 shrink-0 text-green-500" }),
    /* @__PURE__ */ jsx("div", { className: "text-sm text-green-900 dark:text-green-100 [&>p]:mb-2 [&>p:last-child]:mb-0", children })
  ] }) });
}
function Accordion({
  title,
  children
}) {
  const [isOpen, setIsOpen] = React.useState(false);
  return /* @__PURE__ */ jsxs("div", { className: "my-3 rounded-lg border border-slate-700", children: [
    /* @__PURE__ */ jsxs(
      "button",
      {
        onClick: () => setIsOpen(!isOpen),
        className: "flex w-full items-center justify-between p-3 text-left text-sm font-medium transition-colors hover:bg-slate-700/50",
        children: [
          /* @__PURE__ */ jsx("span", { children: title }),
          /* @__PURE__ */ jsx(
            ChevronDown,
            {
              className: cn("size-4 transition-transform", isOpen && "rotate-180")
            }
          )
        ]
      }
    ),
    isOpen && /* @__PURE__ */ jsx("div", { className: "border-t border-slate-700 p-3 pt-0 text-sm text-slate-400", children })
  ] });
}
function Tabs({ children }) {
  const [activeTab, setActiveTab] = React.useState(0);
  const tabs = React.Children.toArray(children).filter(
    (child) => React.isValidElement(child)
  );
  const tabTitles = tabs.map((tab, index) => {
    if (React.isValidElement(tab)) {
      return tab.props.title || `Tab ${index + 1}`;
    }
    return `Tab ${index + 1}`;
  });
  return /* @__PURE__ */ jsxs("div", { className: "my-4", children: [
    /* @__PURE__ */ jsx("div", { className: "flex gap-1 overflow-x-auto border-b border-slate-700", children: tabTitles.map((title, index) => /* @__PURE__ */ jsx(
      "button",
      {
        onClick: () => setActiveTab(index),
        className: cn(
          "px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors",
          activeTab === index ? "border-b-2 border-slate-500 text-slate-300" : "text-slate-400 hover:text-slate-100"
        ),
        children: title
      },
      index
    )) }),
    /* @__PURE__ */ jsx("div", { className: "mt-3", children: tabs[activeTab] })
  ] });
}
function Tab({ children }) {
  return /* @__PURE__ */ jsx("div", { children });
}
const mdxComponents = {
  Card,
  CardGroup,
  Steps,
  Step,
  CodeBlocks,
  CodeGroup,
  CodeBlock,
  Warning,
  Note,
  Tip,
  Accordion,
  Tabs,
  Tab,
  // Icons removed - renders nothing
  Icon: () => null,
  h1: ({ children, ...props }) => /* @__PURE__ */ jsx("h1", { className: "mt-4 mb-3 text-xl font-bold first:mt-0", ...props, children }),
  h2: ({ children, ...props }) => /* @__PURE__ */ jsx("h2", { className: "mt-4 mb-2 text-lg font-semibold first:mt-0", ...props, children }),
  h3: ({ children, ...props }) => /* @__PURE__ */ jsx("h3", { className: "mt-3 mb-2 text-base font-semibold", ...props, children }),
  h4: ({ children, ...props }) => /* @__PURE__ */ jsx("h4", { className: "mt-2 mb-1 text-sm font-semibold", ...props, children }),
  p: ({ children, ...props }) => /* @__PURE__ */ jsx("p", { className: "mb-3 text-sm leading-relaxed text-slate-400", ...props, children }),
  ul: ({ children, ...props }) => /* @__PURE__ */ jsx("ul", { className: "mb-3 list-inside list-disc space-y-1 text-sm", ...props, children }),
  ol: ({ children, ...props }) => /* @__PURE__ */ jsx("ol", { className: "mb-3 list-inside list-decimal space-y-1 text-sm", ...props, children }),
  li: ({ children, ...props }) => /* @__PURE__ */ jsx("li", { className: "text-slate-400", ...props, children }),
  a: ({ href, children, ...props }) => {
    const finalHref = href?.startsWith("http") ? href : `${DOCS_BASE_URL}${href}`;
    return /* @__PURE__ */ jsx(
      "a",
      {
        href: finalHref,
        target: "_blank",
        rel: "noopener noreferrer",
        className: "text-slate-300 hover:underline",
        ...props,
        children
      }
    );
  },
  pre: ({ children, ...props }) => /* @__PURE__ */ jsx(
    "pre",
    {
      className: "mb-3 overflow-auto rounded-lg bg-slate-800 p-3 text-xs",
      ...props,
      children
    }
  ),
  code: ({ children, ...props }) => {
    const isInline = !props.className;
    if (isInline) {
      return /* @__PURE__ */ jsx(
        "code",
        {
          className: "rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs",
          ...props,
          children
        }
      );
    }
    return /* @__PURE__ */ jsx("code", { className: "font-mono text-xs", ...props, children });
  },
  blockquote: ({ children, ...props }) => /* @__PURE__ */ jsx(
    "blockquote",
    {
      className: "mb-3 border-l-2 border-slate-500 pl-4 text-sm text-slate-400 italic",
      ...props,
      children
    }
  ),
  hr: (props) => /* @__PURE__ */ jsx("hr", { className: "my-4 border-slate-700", ...props }),
  table: ({ children, ...props }) => /* @__PURE__ */ jsx("div", { className: "mb-3 overflow-auto", children: /* @__PURE__ */ jsx("table", { className: "w-full text-sm", ...props, children }) }),
  th: ({ children, ...props }) => /* @__PURE__ */ jsx(
    "th",
    {
      className: "border border-slate-700 bg-slate-800 px-3 py-2 text-left font-semibold",
      ...props,
      children
    }
  ),
  td: ({ children, ...props }) => /* @__PURE__ */ jsx("td", { className: "border border-slate-700 px-3 py-2", ...props, children }),
  video: (props) => /* @__PURE__ */ jsx("video", { className: "my-3 max-w-full rounded-lg", ...props }),
  strong: ({ children, ...props }) => /* @__PURE__ */ jsx("strong", { className: "font-semibold text-slate-100", ...props, children }),
  em: ({ children, ...props }) => /* @__PURE__ */ jsx("em", { className: "italic", ...props, children })
};
const emptyComponents = {};
const MDXContext = React__default.createContext(emptyComponents);
function useMDXComponents(components) {
  const contextComponents = React__default.useContext(MDXContext);
  return React__default.useMemo(
    function() {
      if (typeof components === "function") {
        return components(contextComponents);
      }
      return { ...contextComponents, ...components };
    },
    [contextComponents, components]
  );
}
function MDXProvider(properties) {
  let allComponents;
  if (properties.disableParentContext) {
    allComponents = typeof properties.components === "function" ? properties.components(emptyComponents) : properties.components || emptyComponents;
  } else {
    allComponents = useMDXComponents(properties.components);
  }
  return React__default.createElement(
    MDXContext.Provider,
    { value: allComponents },
    properties.children
  );
}
function MdxProvider({ children }) {
  return /* @__PURE__ */ jsx(MDXProvider, { components: mdxComponents, children });
}
const mdxModules = /* @__PURE__ */ Object.assign({ "../../../fern/docs/pages/add-new-source.mdx": () => import("./add-new-source-BNEV72e1.mjs"), "../../../fern/docs/pages/auth-providers/composio.mdx": () => import("./composio-DllX5pOn.mjs"), "../../../fern/docs/pages/auth-providers/overview.mdx": () => import("./overview-R80vndxP.mjs"), "../../../fern/docs/pages/auth-providers/pipedream.mdx": () => import("./pipedream-B_j1sX90.mjs"), "../../../fern/docs/pages/concepts.mdx": () => import("./concepts-DcTqCZZs.mjs"), "../../../fern/docs/pages/connecting-sources/direct-oauth.mdx": () => import("./direct-oauth-1O2yQTon.mjs"), "../../../fern/docs/pages/connectors/airtable/main.mdx": () => import("./main-BLLPYo_E.mjs"), "../../../fern/docs/pages/connectors/asana/main.mdx": () => import("./main-DV9DXDAb.mjs"), "../../../fern/docs/pages/connectors/attio/main.mdx": () => import("./main-DFm-8EiW.mjs"), "../../../fern/docs/pages/connectors/bitbucket/main.mdx": () => import("./main-D2_3F0OB.mjs"), "../../../fern/docs/pages/connectors/box/main.mdx": () => import("./main-CCWR5cVa.mjs"), "../../../fern/docs/pages/connectors/clickup/main.mdx": () => import("./main-DnhlPkKC.mjs"), "../../../fern/docs/pages/connectors/confluence/main.mdx": () => import("./main-DNgCeN98.mjs"), "../../../fern/docs/pages/connectors/ctti/main.mdx": () => import("./main-CFtAQeh3.mjs"), "../../../fern/docs/pages/connectors/dropbox/main.mdx": () => import("./main-CVCiVF2S.mjs"), "../../../fern/docs/pages/connectors/elasticsearch/main.mdx": () => import("./main-yxZg8I7S.mjs"), "../../../fern/docs/pages/connectors/excel/main.mdx": () => import("./main-Dqy7OM1-.mjs"), "../../../fern/docs/pages/connectors/github/main.mdx": () => import("./main-CL-aI4TH.mjs"), "../../../fern/docs/pages/connectors/gitlab/main.mdx": () => import("./main-CHcEoah6.mjs"), "../../../fern/docs/pages/connectors/gmail/main.mdx": () => import("./main-D1v8nYUb.mjs"), "../../../fern/docs/pages/connectors/google_calendar/main.mdx": () => import("./main-GwRgjyjH.mjs"), "../../../fern/docs/pages/connectors/google_docs/main.mdx": () => import("./main-C-HNur_V.mjs"), "../../../fern/docs/pages/connectors/google_drive/main.mdx": () => import("./main-ChG7wKug.mjs"), "../../../fern/docs/pages/connectors/google_slides/main.mdx": () => import("./main-DNPFjBT2.mjs"), "../../../fern/docs/pages/connectors/hubspot/main.mdx": () => import("./main-DZQMjiQN.mjs"), "../../../fern/docs/pages/connectors/intercom/main.mdx": () => import("./main-BOi1dk6K.mjs"), "../../../fern/docs/pages/connectors/jira/main.mdx": () => import("./main-CVX0hrhN.mjs"), "../../../fern/docs/pages/connectors/linear/main.mdx": () => import("./main-BMaAkeZE.mjs"), "../../../fern/docs/pages/connectors/monday/main.mdx": () => import("./main-IO0MqYLs.mjs"), "../../../fern/docs/pages/connectors/mysql/main.mdx": () => import("./main-B_3GJV-Z.mjs"), "../../../fern/docs/pages/connectors/notion/main.mdx": () => import("./main-Bpbz3gFb.mjs"), "../../../fern/docs/pages/connectors/onedrive/main.mdx": () => import("./main-ClYepf3n.mjs"), "../../../fern/docs/pages/connectors/onenote/main.mdx": () => import("./main-CRUGTWjT.mjs"), "../../../fern/docs/pages/connectors/oracle/main.mdx": () => import("./main-a_q662pd.mjs"), "../../../fern/docs/pages/connectors/outlook_calendar/main.mdx": () => import("./main-DI73SwVK.mjs"), "../../../fern/docs/pages/connectors/outlook_mail/main.mdx": () => import("./main-BNmafd2F.mjs"), "../../../fern/docs/pages/connectors/postgresql/main.mdx": () => import("./main-Drfbd5wz.mjs"), "../../../fern/docs/pages/connectors/salesforce/main.mdx": () => import("./main-BXTWEbic.mjs"), "../../../fern/docs/pages/connectors/sharepoint/main.mdx": () => import("./main-DIQIk2ok.mjs"), "../../../fern/docs/pages/connectors/slack/main.mdx": () => import("./main-BQkVmTup.mjs"), "../../../fern/docs/pages/connectors/sql_server/main.mdx": () => import("./main-BWPft48a.mjs"), "../../../fern/docs/pages/connectors/sqlite/main.mdx": () => import("./main-PLHWgO82.mjs"), "../../../fern/docs/pages/connectors/stripe/main.mdx": () => import("./main-CnXM8ZPT.mjs"), "../../../fern/docs/pages/connectors/teams/main.mdx": () => import("./main-BAE3_rQk.mjs"), "../../../fern/docs/pages/connectors/todoist/main.mdx": () => import("./main-BoIWaOGD.mjs"), "../../../fern/docs/pages/connectors/trello/main.mdx": () => import("./main-B9S4xxLg.mjs"), "../../../fern/docs/pages/connectors/word/main.mdx": () => import("./main-CgFVgfLI.mjs"), "../../../fern/docs/pages/connectors/zendesk/main.mdx": () => import("./main-By52ljQx.mjs"), "../../../fern/docs/pages/direct-token-injection.mdx": () => import("./direct-token-injection-BL5K0gnn.mjs"), "../../../fern/docs/pages/framework-integrations/llamaindex.mdx": () => import("./llamaindex-nLdYLbtl.mjs"), "../../../fern/docs/pages/framework-integrations/vercel-ai-sdk.mdx": () => import("./vercel-ai-sdk-DGK3M3dy.mjs"), "../../../fern/docs/pages/mcp-server.mdx": () => import("./mcp-server-CyCiXC9j.mjs"), "../../../fern/docs/pages/quickstart.mdx": () => import("./quickstart-DYN5CJyY.mjs"), "../../../fern/docs/pages/rate-limits.mdx": () => import("./rate-limits-CDw09bW4.mjs"), "../../../fern/docs/pages/search.mdx": () => import("./search-a028w_M9.mjs"), "../../../fern/docs/pages/search/concepts.mdx": () => import("./concepts-CDJ-Y7VD.mjs"), "../../../fern/docs/pages/search/examples.mdx": () => import("./examples-D8fsgl07.mjs"), "../../../fern/docs/pages/search/filters.mdx": () => import("./filters-BF_yrtgZ.mjs"), "../../../fern/docs/pages/welcome.mdx": () => import("./welcome-B1HYxCKd.mjs") });
async function loadMdxModule(docPath) {
  const fullPath = `../../../fern/docs/pages/${docPath}`;
  const moduleLoader = mdxModules[fullPath];
  if (!moduleLoader) {
    throw new Error(`Documentation not found: ${docPath}`);
  }
  const module = await moduleLoader();
  return {
    Component: module.default,
    frontmatter: module.frontmatter
  };
}
function useDocsContent(docPath) {
  const {
    data,
    isLoading: loading,
    error
  } = useQuery({
    queryKey: ["docs-content", docPath],
    queryFn: () => loadMdxModule(docPath),
    enabled: !!docPath,
    staleTime: Infinity,
    // MDX content doesn't change at runtime
    gcTime: Infinity
    // Keep cached indefinitely
  });
  const content = React.useMemo(() => {
    if (!data) return null;
    const { Component } = data;
    return /* @__PURE__ */ jsx(MdxProvider, { children: /* @__PURE__ */ jsx(Component, {}) });
  }, [data]);
  return {
    content,
    loading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
    title: data?.frontmatter?.title
  };
}
function DocsContent({
  docPath,
  fallback
}) {
  const { content, loading, error } = useDocsContent(docPath);
  if (loading) {
    return /* @__PURE__ */ jsx("div", { className: "flex items-center justify-center py-8", children: /* @__PURE__ */ jsx("div", { className: "animate-pulse text-sm text-slate-400", children: "Loading documentation..." }) });
  }
  if (error) {
    return /* @__PURE__ */ jsx("div", { className: "py-4 text-sm text-slate-400", children: fallback || "Documentation not available." });
  }
  if (!content) {
    return /* @__PURE__ */ jsx("div", { className: "py-4 text-sm text-slate-400", children: fallback || "No documentation available for this page." });
  }
  return /* @__PURE__ */ jsx(Fragment, { children: content });
}
export {
  ChevronDown as C,
  DocsContent as D,
  formatDate as f,
  getDaysFromNow as g,
  useMDXComponents as u
};
