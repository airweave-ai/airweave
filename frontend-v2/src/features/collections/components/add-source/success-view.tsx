/**
 * SuccessView - Confirmation after source connection is created
 */

import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, CheckCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useIsDark } from "@/hooks/use-is-dark";
import { useOrg } from "@/lib/org-context";
import { cn } from "@/lib/utils";

interface SuccessViewProps {
  collectionId: string;
  collectionName: string;
  sourceName: string;
  onClose: () => void;
}

export function SuccessView({
  collectionId,
  collectionName,
  sourceName,
  onClose,
}: SuccessViewProps) {
  const isDark = useIsDark();
  const navigate = useNavigate();
  const { getOrgSlug, organization } = useOrg();

  const handleViewCollection = () => {
    if (organization) {
      const orgSlug = getOrgSlug(organization);
      navigate({ to: `/${orgSlug}/collections/${collectionId}` });
    }
    onClose();
  };

  return (
    <div className="flex h-full flex-col items-center justify-center px-6 py-12">
      <div className="max-w-sm space-y-6 text-center">
        {/* Success icon */}
        <div
          className={cn(
            "mx-auto flex h-20 w-20 items-center justify-center rounded-full",
            isDark ? "bg-green-900/30" : "bg-green-100"
          )}
        >
          <CheckCircle
            className={cn(
              "h-10 w-10",
              isDark ? "text-green-400" : "text-green-600"
            )}
          />
        </div>

        {/* Success message */}
        <div>
          <h2
            className={cn(
              "text-2xl font-semibold",
              isDark ? "text-white" : "text-gray-900"
            )}
          >
            Source connected!
          </h2>
          <p className={cn("mt-2", isDark ? "text-gray-400" : "text-gray-600")}>
            Your data is now syncing
          </p>
        </div>

        {/* Connection info */}
        <div
          className={cn(
            "rounded-lg border p-4",
            isDark
              ? "border-gray-700 bg-gray-800/50"
              : "border-gray-200 bg-gray-50"
          )}
        >
          <div className="space-y-2 text-left">
            <div className="flex items-center justify-between text-sm">
              <span className={cn(isDark ? "text-gray-400" : "text-gray-500")}>
                Collection
              </span>
              <span className="font-medium">{collectionName}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className={cn(isDark ? "text-gray-400" : "text-gray-500")}>
                Source
              </span>
              <span className="font-medium">{sourceName}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className={cn(isDark ? "text-gray-400" : "text-gray-500")}>
                Status
              </span>
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "h-2 w-2 animate-pulse rounded-full",
                    "bg-green-500"
                  )}
                />
                <span
                  className={cn(
                    "font-medium",
                    isDark ? "text-green-400" : "text-green-600"
                  )}
                >
                  Syncing
                </span>
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-3">
          <Button
            onClick={handleViewCollection}
            className="w-full bg-blue-600 text-white hover:bg-blue-700"
          >
            View Collection
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>

          <button
            onClick={onClose}
            className={cn(
              "w-full rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              isDark
                ? "text-gray-400 hover:text-gray-200"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
