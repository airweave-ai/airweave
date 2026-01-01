import { CheckCircle2, Copy, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { APIKey } from "@/lib/api";

import {
  formatDate,
  getDaysRemaining,
  getStatusColor,
  maskKey,
} from "../utils/helpers";

interface ApiKeyItemProps {
  apiKey: APIKey;
  onDelete: (keyId: string) => void;
}

export function ApiKeyItem({ apiKey, onDelete }: ApiKeyItemProps) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const daysRemaining = getDaysRemaining(apiKey.expiration_date);
  const isExpired = daysRemaining < 0;
  const isExpiringSoon = daysRemaining >= 0 && daysRemaining <= 7;

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(
      () => {
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
      },
      () => {
        console.error("Failed to copy key");
      },
    );
  };

  return (
    <div
      className={`rounded-lg border bg-card ${
        isExpired ? "border-red-200 dark:border-red-900/50" : ""
      }`}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          {/* Key Info */}
          <div className="flex-1 min-w-0 space-y-3">
            <div className="flex items-center gap-3">
              <code className="text-xs font-mono font-medium">
                {maskKey(apiKey.decrypted_key)}
              </code>
              {isExpired && (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                  Expired
                </span>
              )}
              {isExpiringSoon && !isExpired && (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                  Expiring soon
                </span>
              )}
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>Created {formatDate(apiKey.created_at)}</span>
              <span className="text-muted-foreground/50">•</span>
              <span className={getStatusColor(daysRemaining)}>
                {isExpired
                  ? `Expired ${Math.abs(daysRemaining)} day${Math.abs(daysRemaining) === 1 ? "" : "s"} ago`
                  : `Expires in ${daysRemaining} day${daysRemaining === 1 ? "" : "s"}`}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleCopyKey(apiKey.decrypted_key)}
              className="size-8"
              title="Copy key"
            >
              {copiedKey === apiKey.decrypted_key ? (
                <CheckCircle2 className="size-4" />
              ) : (
                <Copy className="size-4" />
              )}
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 text-muted-foreground hover:text-red-600 dark:hover:text-red-500"
                  title="Delete key"
                >
                  <Trash2 className="size-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="sm:max-w-md">
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete API key</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone. Any applications using this
                    key will lose access immediately.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="my-4 rounded-lg border bg-muted p-3">
                  <code className="text-sm font-mono">
                    {maskKey(apiKey.decrypted_key)}
                  </code>
                </div>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    variant="destructive"
                    onClick={() => onDelete(apiKey.id)}
                  >
                    Delete key
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </div>
    </div>
  );
}

