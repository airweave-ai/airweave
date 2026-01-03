import { AlertTriangle, ChevronDown, Info, Lightbulb } from "lucide-react";
import type { MDXComponents } from "mdx/types";
import * as React from "react";

import { cn } from "@/lib/utils";

const DOCS_BASE_URL = "https://docs.airweave.ai";

// Card component (without icon support)
function Card({
  title,
  href,
  children,
}: {
  title: string;
  href?: string;
  children?: React.ReactNode;
}) {
  const content = (
    <div className="bg-card hover:bg-muted/50 h-full rounded-lg border p-4 transition-colors">
      <h4 className="mb-1 text-sm font-semibold">{title}</h4>
      {children && (
        <div className="text-muted-foreground text-xs">{children}</div>
      )}
    </div>
  );

  if (href) {
    // All links open in new tab - relative links get docs base URL prepended
    const finalHref = href.startsWith("http")
      ? href
      : `${DOCS_BASE_URL}${href}`;
    return (
      <a
        href={finalHref}
        target="_blank"
        rel="noopener noreferrer"
        className="block no-underline"
      >
        {content}
      </a>
    );
  }

  return content;
}

// CardGroup component
function CardGroup({
  cols = 2,
  children,
}: {
  cols?: number;
  children: React.ReactNode;
}) {
  const gridCols =
    {
      1: "grid-cols-1",
      2: "grid-cols-1 sm:grid-cols-2",
      3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
    }[cols] || "grid-cols-1 sm:grid-cols-2";

  return <div className={cn("my-4 grid gap-3", gridCols)}>{children}</div>;
}

// Steps container
function Steps({ children }: { children: React.ReactNode }) {
  return <div className="my-4 space-y-4">{children}</div>;
}

// Step component
function Step({
  title,
  children,
}: {
  title: string;
  toc?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="border-primary border-l-2 py-2 pl-4">
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      <div className="text-muted-foreground text-sm">{children}</div>
    </div>
  );
}

// CodeBlocks - tabbed code display
function CodeBlocks({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = React.useState(0);
  const blocks = React.Children.toArray(children).filter(
    (child) => React.isValidElement(child) && child.type === "pre"
  );

  if (blocks.length === 0) {
    return <div className="space-y-2">{children}</div>;
  }

  // Extract titles from code blocks
  const tabs = blocks.map((block, index) => {
    if (React.isValidElement(block)) {
      const blockProps = block.props as { children?: React.ReactNode };
      const codeElement = blockProps.children;
      if (React.isValidElement(codeElement)) {
        const title =
          (codeElement.props as { title?: string }).title || `Tab ${index + 1}`;
        return title;
      }
    }
    return `Tab ${index + 1}`;
  });

  return (
    <div className="my-3">
      <div className="flex gap-1 border-b">
        {tabs.map((tab, index) => (
          <button
            key={index}
            onClick={() => setActiveTab(index)}
            className={cn(
              "px-3 py-1 text-xs font-medium transition-colors",
              activeTab === index
                ? "border-primary text-primary border-b-2"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab}
          </button>
        ))}
      </div>
      <div className="mt-2">{blocks[activeTab]}</div>
    </div>
  );
}

// CodeGroup - alias for CodeBlocks
const CodeGroup = CodeBlocks;

// CodeBlock - single code block with title (renders as-is, title handled by code element)
function CodeBlock({
  children,
}: {
  children: React.ReactNode;
  title?: string;
}) {
  return <div className="my-3">{children}</div>;
}

// Warning callout
function Warning({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 rounded-lg border border-amber-500/50 bg-amber-500/10 p-4">
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-500" />
        <div className="text-sm text-amber-900 dark:text-amber-100 [&>p]:mb-2 [&>p:last-child]:mb-0">
          {children}
        </div>
      </div>
    </div>
  );
}

// Note callout
function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 rounded-lg border border-blue-500/50 bg-blue-500/10 p-4">
      <div className="flex gap-3">
        <Info className="mt-0.5 size-5 shrink-0 text-blue-500" />
        <div className="text-sm text-blue-900 dark:text-blue-100 [&>p]:mb-2 [&>p:last-child]:mb-0">
          {children}
        </div>
      </div>
    </div>
  );
}

// Tip callout
function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 rounded-lg border border-green-500/50 bg-green-500/10 p-4">
      <div className="flex gap-3">
        <Lightbulb className="mt-0.5 size-5 shrink-0 text-green-500" />
        <div className="text-sm text-green-900 dark:text-green-100 [&>p]:mb-2 [&>p:last-child]:mb-0">
          {children}
        </div>
      </div>
    </div>
  );
}

// Accordion component
function Accordion({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <div className="my-3 rounded-lg border">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="hover:bg-muted/50 flex w-full items-center justify-between p-3 text-left text-sm font-medium transition-colors"
      >
        <span>{title}</span>
        <ChevronDown
          className={cn("size-4 transition-transform", isOpen && "rotate-180")}
        />
      </button>
      {isOpen && (
        <div className="text-muted-foreground border-t p-3 pt-0 text-sm">
          {children}
        </div>
      )}
    </div>
  );
}

// Tabs container
function Tabs({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = React.useState(0);
  const tabs = React.Children.toArray(children).filter((child) =>
    React.isValidElement(child)
  );

  // Extract titles from Tab components
  const tabTitles = tabs.map((tab, index) => {
    if (React.isValidElement(tab)) {
      return (tab.props as { title?: string }).title || `Tab ${index + 1}`;
    }
    return `Tab ${index + 1}`;
  });

  return (
    <div className="my-4">
      <div className="flex gap-1 overflow-x-auto border-b">
        {tabTitles.map((title, index) => (
          <button
            key={index}
            onClick={() => setActiveTab(index)}
            className={cn(
              "px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors",
              activeTab === index
                ? "border-primary text-primary border-b-2"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {title}
          </button>
        ))}
      </div>
      <div className="mt-3">{tabs[activeTab]}</div>
    </div>
  );
}

// Tab component (just renders children)
function Tab({ children }: { title?: string; children: React.ReactNode }) {
  return <div>{children}</div>;
}

// Custom components for MDX
export const mdxComponents: MDXComponents = {
  // Custom components
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
  // Icon component - render nothing (icons removed)
  Icon: () => null,

  // Override default elements for styling
  h1: ({ children, ...props }) => (
    <h1 className="mt-4 mb-3 text-xl font-bold first:mt-0" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="mt-4 mb-2 text-lg font-semibold first:mt-0" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mt-3 mb-2 text-base font-semibold" {...props}>
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="mt-2 mb-1 text-sm font-semibold" {...props}>
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p
      className="text-muted-foreground mb-3 text-sm leading-relaxed"
      {...props}
    >
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="mb-3 list-inside list-disc space-y-1 text-sm" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="mb-3 list-inside list-decimal space-y-1 text-sm" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-muted-foreground" {...props}>
      {children}
    </li>
  ),
  a: ({ href, children, ...props }) => {
    // All links open in new tab - relative links get docs base URL prepended
    const finalHref = href?.startsWith("http")
      ? href
      : `${DOCS_BASE_URL}${href}`;
    return (
      <a
        href={finalHref}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
        {...props}
      >
        {children}
      </a>
    );
  },
  pre: ({ children, ...props }) => (
    <pre
      className="bg-muted mb-3 overflow-auto rounded-lg p-3 text-xs"
      {...props}
    >
      {children}
    </pre>
  ),
  code: ({ children, ...props }) => {
    // Check if this is inline code (no className) vs code block
    const isInline = !props.className;
    if (isInline) {
      return (
        <code
          className="bg-muted rounded px-1.5 py-0.5 font-mono text-xs"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className="font-mono text-xs" {...props}>
        {children}
      </code>
    );
  },
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-primary text-muted-foreground mb-3 border-l-2 pl-4 text-sm italic"
      {...props}
    >
      {children}
    </blockquote>
  ),
  hr: (props) => <hr className="border-border my-4" {...props} />,
  table: ({ children, ...props }) => (
    <div className="mb-3 overflow-auto">
      <table className="w-full text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th
      className="border-border bg-muted border px-3 py-2 text-left font-semibold"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border-border border px-3 py-2" {...props}>
      {children}
    </td>
  ),
  // Video component
  video: (props) => <video className="my-3 max-w-full rounded-lg" {...props} />,
  // Strong/Bold
  strong: ({ children, ...props }) => (
    <strong className="text-foreground font-semibold" {...props}>
      {children}
    </strong>
  ),
  // Emphasis/Italic
  em: ({ children, ...props }) => (
    <em className="italic" {...props}>
      {children}
    </em>
  ),
};

export default mdxComponents;
