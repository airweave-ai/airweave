import { createRouter } from "@tanstack/react-router";

// Import the generated route tree
import { routeTree } from "./routeTree.gen";
import type { ConnectSessionContext, SessionError } from "./lib/types";

export interface ConnectRouterContext {
  session: ConnectSessionContext | null;
  sessionError: SessionError | null;
}

// Create a new router instance
export const getRouter = () => {
  const router = createRouter({
    routeTree,
    context: {
      session: null,
      sessionError: null,
    } satisfies ConnectRouterContext,
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof getRouter>;
  }
}
