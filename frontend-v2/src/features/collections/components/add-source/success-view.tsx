/**
 * SuccessView - Confirmation after source connection is created
 */

import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, CheckCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useOrg } from "@/lib/org-context";

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
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
          <CheckCircle className="h-10 w-10 text-green-600 dark:text-green-400" />
        </div>

        {/* Success message */}
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Source connected!
          </h2>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Your data is now syncing
          </p>
        </div>

        {/* Connection info */}
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
          <div className="space-y-2 text-left">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">
                Collection
              </span>
              <span className="font-medium">{collectionName}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Source</span>
              <span className="font-medium">{sourceName}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Status</span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                <span className="font-medium text-green-600 dark:text-green-400">
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
            className="w-full rounded-lg px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
