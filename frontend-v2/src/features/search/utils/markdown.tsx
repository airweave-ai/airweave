/**
 * Markdown parsing utilities for search completion rendering
 */

import type { ReactNode } from "react";

/**
 * Parse inline text for citations, code, bold, italic, and links
 */
function parseInlineText(
  text: string,
  onCitationClick: (idx: number) => void,
  keyBase: string
): ReactNode[] {
  const elements: ReactNode[] = [];

  // Combined regex for all inline patterns
  const combinedRegex =
    /(\[\[(\d+)\]\])|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\[([^\]]+)\]\(([^)]+)\))/g;

  let lastIndex = 0;
  let match;
  let elementKey = 0;

  while ((match = combinedRegex.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIndex) {
      elements.push(text.substring(lastIndex, match.index));
    }

    if (match[1]) {
      // Citation [[N]]
      const citationNum = parseInt(match[2], 10);
      elements.push(
        <button
          key={`cite-${keyBase}-${elementKey++}`}
          onClick={() => onCitationClick(citationNum - 1)}
          className="mx-0.5 inline-flex size-5 items-center justify-center rounded bg-blue-500/20 text-xs font-medium text-blue-400 transition-colors hover:bg-blue-500/30"
          title={`Jump to source ${citationNum}`}
        >
          {citationNum}
        </button>
      );
    } else if (match[3]) {
      // Inline code
      elements.push(
        <code
          key={`code-${keyBase}-${elementKey++}`}
          className="rounded bg-slate-800 px-1.5 py-0.5 text-sm text-slate-200"
        >
          {match[4]}
        </code>
      );
    } else if (match[5]) {
      // Bold
      elements.push(
        <strong key={`bold-${keyBase}-${elementKey++}`}>{match[6]}</strong>
      );
    } else if (match[7]) {
      // Link
      elements.push(
        <a
          key={`link-${keyBase}-${elementKey++}`}
          href={match[9]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 underline hover:text-blue-300"
        >
          {match[8]}
        </a>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    elements.push(text.substring(lastIndex));
  }

  return elements;
}

/**
 * Parse inline content for paragraphs and lists
 */
function parseInlineContent(
  text: string,
  onCitationClick: (idx: number) => void,
  keyBase: number
): ReactNode[] {
  const elements: ReactNode[] = [];

  // Split by paragraphs and process
  const paragraphs = text.split(/\n\n+/);

  paragraphs.forEach((paragraph, pIdx) => {
    if (!paragraph.trim()) return;

    // Check if it's a list item
    const lines = paragraph.split("\n");
    const listItems = lines.filter((line) => /^[-*\d.]\s/.test(line.trim()));

    if (listItems.length > 0 && listItems.length === lines.length) {
      // It's a list
      const listElements = lines.map((line, lineIdx) => {
        const cleanLine = line.replace(/^[-*\d.]\s+/, "");
        return (
          <li key={`li-${keyBase}-${pIdx}-${lineIdx}`}>
            {parseInlineText(
              cleanLine,
              onCitationClick,
              `${keyBase}-${pIdx}-${lineIdx}`
            )}
          </li>
        );
      });
      elements.push(
        <ul
          key={`ul-${keyBase}-${pIdx}`}
          className="my-2 ml-4 list-disc space-y-1"
        >
          {listElements}
        </ul>
      );
    } else {
      // Regular paragraph
      elements.push(
        <p key={`p-${keyBase}-${pIdx}`} className="my-2">
          {parseInlineText(
            paragraph.replace(/\n/g, " "),
            onCitationClick,
            `${keyBase}-${pIdx}`
          )}
        </p>
      );
    }
  });

  return elements;
}

/**
 * Parse markdown content with code blocks and citations
 */
export function parseMarkdownContent(
  content: string,
  onCitationClick: (idx: number) => void
): ReactNode[] {
  const elements: ReactNode[] = [];

  // Regex to find code blocks
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g;

  // Process code blocks first
  let match;
  let lastEnd = 0;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    // Add text before code block
    if (match.index > lastEnd) {
      const textBefore = content.substring(lastEnd, match.index);
      elements.push(
        ...parseInlineContent(textBefore, onCitationClick, elements.length)
      );
    }

    // Add code block
    const language = match[1] || "text";
    const code = match[2];
    elements.push(
      <pre
        key={`code-${elements.length}`}
        className="my-3 overflow-x-auto rounded-lg bg-slate-900 p-4"
      >
        <code className={`language-${language} text-sm text-slate-200`}>
          {code.trim()}
        </code>
      </pre>
    );

    lastEnd = match.index + match[0].length;
  }

  // Add remaining text
  if (lastEnd < content.length) {
    const remainingText = content.substring(lastEnd);
    elements.push(
      ...parseInlineContent(remainingText, onCitationClick, elements.length)
    );
  }

  return elements;
}

/**
 * Format response time in human-readable format
 */
export function formatResponseTime(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
}
