import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/$orgSlug/")({
  beforeLoad: ({ params }) => {
    throw redirect({
      to: "/$orgSlug/collections",
      params: { orgSlug: params.orgSlug },
    });
  },
});
