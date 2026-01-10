/**
 * FederatedSearchInfo - Info card explaining federated search mode
 */

import { Send } from "lucide-react";

export function FederatedSearchInfo() {
  return (
    <div className="rounded-lg border border-blue-800/30 bg-blue-900/10 p-4">
      <div className="flex items-start gap-3">
        <Send className="mt-0.5 size-5 text-blue-400" />
        <div className="flex-1 space-y-2">
          <p className="text-sm text-blue-200/80">
            This source searches the data at query time instead of syncing and
            indexing it beforehand.
          </p>
        </div>
      </div>
    </div>
  );
}
