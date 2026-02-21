import type { ReactNode } from "react";
import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createHead, UnheadProvider } from "@unhead/react/client";
import { SessionProvider } from "../components/SessionProvider";
import appCss from "../styles.css?url";

const head = createHead();

const queryClient = new QueryClient();

// Build runtime config inline script during SSR.
// In production (Docker/K8s), process.env.API_URL is set by the container.
// In local dev, it falls back to the Vite default.
// This replaces the previous /config.js external file approach which was
// intercepted by TanStack Start's SSR catch-all before Nitro could serve it.
const runtimeConfig = typeof process !== "undefined" && process.env?.API_URL
  ? `window.__CONNECT_ENV__=${JSON.stringify({ API_URL: process.env.API_URL })};`
  : "";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: "utf-8",
      },
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1",
      },
      {
        title: "Airweave Connect",
      },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
    scripts: runtimeConfig
      ? [{ children: runtimeConfig }]
      : [],
  }),

  shellComponent: RootDocument,
});

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body style={{ backgroundColor: "var(--connect-bg, transparent)" }}>
        <UnheadProvider head={head}>
          <QueryClientProvider client={queryClient}>
            <SessionProvider />
            {children}
          </QueryClientProvider>
        </UnheadProvider>
        <Scripts />
      </body>
    </html>
  );
}
