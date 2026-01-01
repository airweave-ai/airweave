import {
  BookOpen,
  Brain,
  Database,
  ExternalLink,
  FileText,
  Github,
  Globe,
  Headphones,
  Home,
  Layers,
  Link as LinkIcon,
  MessageSquare,
  Play,
  Plug,
  Rocket,
} from "lucide-react";
import type { MDXComponents } from "mdx/types";
import * as React from "react";

import { cn } from "@/lib/utils";

// Map Font Awesome icons to Lucide icons
const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  "fa-solid fa-rocket": Rocket,
  "fa-solid fa-globe": Globe,
  "fa-brands fa-discord": MessageSquare,
  "fa-brands fa-github": Github,
  "fa-solid fa-brain": Brain,
  "fa-solid fa-headset": Headphones,
  "fa-solid fa-database": Database,
  "fa-solid fa-play": Play,
  "fa-solid fa-book": BookOpen,
  "fa-solid fa-home": Home,
  "fa-solid fa-plug": Plug,
  "fa-solid fa-link": LinkIcon,
  "fa-solid fa-layer-group": Layers,
  "fa-solid fa-file-alt": FileText,
};

// Icon component that maps Font Awesome names to Lucide icons
function Icon({
  icon,
  size = 4,
  className,
}: {
  icon: string;
  size?: number | string;
  color?: string;
  className?: string;
}) {
  const IconComponent = iconMap[icon] || Database;
  const sizeClass = typeof size === "number" ? `size-${size}` : size;
  return <IconComponent className={cn(sizeClass, "inline-block", className)} />;
}

// Card component
function Card({
  title,
  icon,
  href,
  children,
}: {
  title: string;
  icon?: string;
  href?: string;
  children?: React.ReactNode;
}) {
  const content = (
    <div className="rounded-lg border bg-card p-4 hover:bg-muted/50 transition-colors h-full">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="text-primary shrink-0">
            <Icon icon={icon} size={5} />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm mb-1 flex items-center gap-1">
            {title}
            {href?.startsWith("http") && (
              <ExternalLink className="size-3 text-muted-foreground" />
            )}
          </h4>
          {children && (
            <div className="text-xs text-muted-foreground">{children}</div>
          )}
        </div>
      </div>
    </div>
  );

  if (href) {
    const isExternal = href.startsWith("http");
    return (
      <a
        href={href}
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noopener noreferrer" : undefined}
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

  return <div className={cn("grid gap-3 my-4", gridCols)}>{children}</div>;
}

// Steps container
function Steps({ children }: { children: React.ReactNode }) {
  return <div className="space-y-4 my-4">{children}</div>;
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
    <div className="border-l-2 border-primary pl-4 py-2">
      <h4 className="font-semibold text-sm mb-2">{title}</h4>
      <div className="text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

// CodeBlocks - tabbed code display
function CodeBlocks({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = React.useState(0);
  const blocks = React.Children.toArray(children).filter(
    (child) => React.isValidElement(child) && child.type === "pre",
  );

  if (blocks.length === 0) {
    return <div className="space-y-2">{children}</div>;
  }

  // Extract titles from code blocks
  const tabs = blocks.map((block, index) => {
    if (React.isValidElement(block)) {
      const codeElement = block.props.children;
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
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground",
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

// Custom components for MDX
export const mdxComponents: MDXComponents = {
  // Custom components
  Icon,
  Card,
  CardGroup,
  Steps,
  Step,
  CodeBlocks,

  // Override default elements for styling
  h1: ({ children, ...props }) => (
    <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="text-lg font-semibold mb-2 mt-4 first:mt-0" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="text-base font-semibold mb-2 mt-3" {...props}>
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="text-sm font-semibold mb-1 mt-2" {...props}>
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p
      className="text-sm text-muted-foreground mb-3 leading-relaxed"
      {...props}
    >
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="text-sm list-disc list-inside mb-3 space-y-1" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="text-sm list-decimal list-inside mb-3 space-y-1" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-muted-foreground" {...props}>
      {children}
    </li>
  ),
  a: ({ href, children, ...props }) => {
    const isExternal = href?.startsWith("http");
    return (
      <a
        href={href}
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noopener noreferrer" : undefined}
        className="text-primary hover:underline inline-flex items-center gap-1"
        {...props}
      >
        {children}
        {isExternal && <ExternalLink className="size-3" />}
      </a>
    );
  },
  pre: ({ children, ...props }) => (
    <pre
      className="bg-muted p-3 rounded-lg text-xs overflow-auto mb-3"
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
          className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className="text-xs font-mono" {...props}>
        {children}
      </code>
    );
  },
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-l-2 border-primary pl-4 italic text-sm text-muted-foreground mb-3"
      {...props}
    >
      {children}
    </blockquote>
  ),
  hr: (props) => <hr className="my-4 border-border" {...props} />,
  table: ({ children, ...props }) => (
    <div className="overflow-auto mb-3">
      <table className="w-full text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th
      className="border border-border px-3 py-2 text-left font-semibold bg-muted"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border border-border px-3 py-2" {...props}>
      {children}
    </td>
  ),
  // Video component
  video: (props) => <video className="rounded-lg max-w-full my-3" {...props} />,
  // Strong/Bold
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-foreground" {...props}>
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
