import { marked } from "marked";

const SAFE_PROTOCOLS = ["http:", "https:", "mailto:"];

function isSafeUrl(href: string): boolean {
  try {
    const url = new URL(href, window.location.origin);
    return SAFE_PROTOCOLS.includes(url.protocol);
  } catch {
    return false;
  }
}

const renderer = new marked.Renderer();
renderer.link = ({ href, text }) => {
  if (!isSafeUrl(href)) {
    return text;
  }
  return `<a href="${href}" target="_blank" rel="noopener noreferrer" style="text-decoration: underline; font-weight: 500;">${text}</a>`;
};
marked.use({ renderer });

export function parseInlineMarkdown(text: string): string {
  return marked.parseInline(text) as string;
}
