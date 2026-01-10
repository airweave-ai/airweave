import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  CloudUpload,
  Loader2,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { S3ConfigModal } from "@/components/s3-config-modal";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { deleteS3Config, fetchS3Status } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";

const S3_DESTINATION_FEATURE = "S3_DESTINATION";

export function S3StatusCard() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();

  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const hasFeature = organization?.enabled_features?.includes(
    S3_DESTINATION_FEATURE
  );

  const {
    data: status,
    isLoading,
    error,
  } = useQuery({
    queryKey: queryKeys.s3.status(organization?.id ?? ""),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchS3Status(token, organization!.id);
    },
    enabled: !!organization?.id && hasFeature,
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteS3Config(token, organization!.id);
    },
    onSuccess: () => {
      toast.success("S3 configuration removed");
      setShowDeleteConfirm(false);
      queryClient.invalidateQueries({
        queryKey: queryKeys.s3.status(organization!.id),
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to remove S3 configuration"
      );
    },
  });

  // Don't render if feature not enabled
  if (!hasFeature) {
    return null;
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudUpload className="size-5" />
            S3 Event Streaming
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-muted-foreground flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" />
            Loading S3 configuration...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudUpload className="size-5" />
            S3 Event Streaming
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-destructive text-sm">
            Failed to load S3 configuration
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <CloudUpload className="text-primary size-5" />
                S3 Event Streaming
              </CardTitle>
              <CardDescription>
                Sync all collections to S3 for real-time event streaming and
                archival
              </CardDescription>
            </div>
            {status?.configured && (
              <Badge
                variant="outline"
                className="border-green-200 bg-green-50 text-green-700"
              >
                <CheckCircle2 className="mr-1 size-3" />
                Configured
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {!status?.configured ? (
            <>
              <Alert>
                <AlertCircle className="size-4" />
                <AlertDescription>
                  S3 destination is not configured. Set up your S3 bucket to
                  enable event streaming for all collections.
                </AlertDescription>
              </Alert>

              <Button
                onClick={() => setShowConfigModal(true)}
                className="w-full"
              >
                <CloudUpload className="mr-2 size-4" />
                Configure S3 Destination
              </Button>

              <div className="text-muted-foreground space-y-1 text-xs">
                <p className="font-medium">Supported Storage:</p>
                <ul className="ml-2 list-inside list-disc space-y-0.5">
                  <li>AWS S3</li>
                  <li>MinIO (self-hosted)</li>
                  <li>Cloudflare R2</li>
                  <li>Any S3-compatible storage</li>
                </ul>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Bucket</span>
                  <span className="font-mono font-medium">
                    {status.bucket_name}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <Badge variant="outline">{status.status || "ACTIVE"}</Badge>
                </div>
                {status.created_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Configured</span>
                    <span className="text-muted-foreground">
                      {new Date(status.created_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              <Alert className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950">
                <CheckCircle2 className="size-4 text-blue-600" />
                <AlertDescription className="text-blue-600 dark:text-blue-400">
                  All syncs automatically write to both Qdrant (search) and S3
                  (events).
                </AlertDescription>
              </Alert>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setShowConfigModal(true)}
                  className="flex-1"
                >
                  Update Configuration
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>

              {showDeleteConfirm && (
                <Alert variant="destructive">
                  <AlertDescription className="space-y-3">
                    <p className="font-medium">Are you sure?</p>
                    <p className="text-sm">
                      This will remove S3 destination. Future syncs will only
                      write to Qdrant. Existing data in S3 will not be deleted.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => deleteMutation.mutate()}
                        disabled={deleteMutation.isPending}
                      >
                        {deleteMutation.isPending
                          ? "Removing..."
                          : "Yes, Remove S3 Configuration"}
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <S3ConfigModal open={showConfigModal} onOpenChange={setShowConfigModal} />
    </>
  );
}
