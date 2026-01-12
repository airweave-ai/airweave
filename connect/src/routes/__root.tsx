import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router";
import { SessionProvider } from "../components/SessionProvider";
import appCss from "../styles.css?url";

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
  }),

  shellComponent: RootDocument,
});

function RootDocument() {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body style={{ backgroundColor: "var(--connect-bg, #0f172a)" }}>
        <SessionProvider />
        <Scripts />
      </body>
    </html>
  );
}
