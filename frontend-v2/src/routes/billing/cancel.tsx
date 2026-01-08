import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useIsDark } from "@/hooks/use-is-dark";

export const Route = createFileRoute("/billing/cancel")({
  component: BillingCancelPage,
});

function BillingCancelPage() {
  const navigate = useNavigate();
  const isDark = useIsDark();

  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-12 text-center">
          <img
            src={
              isDark
                ? "/airweave-logo-svg-white-darkbg.svg"
                : "/airweave-logo-svg-lightbg-blacklogo.svg"
            }
            alt="Airweave"
            className="mx-auto mb-2 h-8 w-auto"
            style={{ maxWidth: "180px" }}
          />
          <p className="text-muted-foreground text-xs">Build smarter agents</p>
        </div>

        <div className="space-y-8 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-50 dark:bg-red-950/20">
            <XCircle className="h-8 w-8 text-red-600 dark:text-red-500" />
          </div>

          <div className="space-y-3">
            <h1 className="text-2xl font-normal">Payment Cancelled</h1>
            <p className="text-muted-foreground">
              Your payment was cancelled and no charges were made
            </p>
          </div>

          <div className="space-y-6">
            <p className="text-muted-foreground text-sm">
              You can still use Airweave with limited features, or complete your
              subscription setup anytime from your organization settings.
            </p>

            <Button
              onClick={() => navigate({ to: "/" })}
              className="w-full"
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              Continue to Dashboard
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
