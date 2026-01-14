import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: ConnectHome,
});

function ConnectHome() {
  // The SessionProvider handles all UI states (loading, error, success)
  // This component will later show the integration list for valid sessions
  return null;
}
