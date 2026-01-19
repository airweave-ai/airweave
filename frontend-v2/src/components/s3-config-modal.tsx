import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CloudUpload, Loader2, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { configureS3, S3ConfigRequest, testS3Connection } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";

interface S3ConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type Step = "configure" | "testing" | "success";

interface S3FormData {
  aws_access_key_id: string;
  aws_secret_access_key: string;
  bucket_name: string;
  bucket_prefix: string;
  aws_region: string;
  endpoint_url: string;
  use_ssl: boolean;
}

const initialFormData: S3FormData = {
  aws_access_key_id: "",
  aws_secret_access_key: "",
  bucket_name: "",
  bucket_prefix: "airweave-outbound/",
  aws_region: "us-east-1",
  endpoint_url: "",
  use_ssl: true,
};

export function S3ConfigModal({ open, onOpenChange }: S3ConfigModalProps) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>("configure");
  const [formData, setFormData] = useState<S3FormData>(initialFormData);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const getConfigPayload = (): S3ConfigRequest => ({
    ...formData,
    endpoint_url: formData.endpoint_url.trim() || null,
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return testS3Connection(token, organization!.id, getConfigPayload());
    },
    onSuccess: (result) => {
      setTestResult({ success: true, message: result.message });
      setStep("testing");
    },
    onError: (error) => {
      setTestResult({
        success: false,
        message:
          error instanceof Error ? error.message : "Failed to connect to S3",
      });
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return configureS3(token, organization!.id, getConfigPayload());
    },
    onSuccess: () => {
      setStep("success");
      queryClient.invalidateQueries({
        queryKey: queryKeys.s3.status(organization!.id),
      });
      toast.success("S3 destination configured successfully");

      setTimeout(() => {
        handleClose();
      }, 2000);
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to save S3 configuration"
      );
    },
  });

  const handleClose = () => {
    setStep("configure");
    setFormData(initialFormData);
    setTestResult(null);
    setShowAdvanced(false);
    onOpenChange(false);
  };

  const isFormValid =
    formData.aws_access_key_id.trim() !== "" &&
    formData.aws_secret_access_key.trim() !== "" &&
    formData.bucket_name.trim() !== "";

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CloudUpload className="text-primary size-5" />
            Configure S3
          </DialogTitle>
          <DialogDescription>
            Set up S3-compatible storage for streaming and archival
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {step === "configure" && (
            <>
              <div className="space-y-4">
                {/* AWS Credentials */}
                <div className="space-y-2">
                  <Label htmlFor="aws_access_key_id">AWS Access Key ID *</Label>
                  <Input
                    id="aws_access_key_id"
                    type="text"
                    placeholder="AKIAIOSFODNN7EXAMPLE"
                    value={formData.aws_access_key_id}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        aws_access_key_id: e.target.value,
                      })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="aws_secret_access_key">
                    AWS Secret Access Key *
                  </Label>
                  <Input
                    id="aws_secret_access_key"
                    type="password"
                    placeholder="wJalrXUtnFEMI/K7MDENG/..."
                    value={formData.aws_secret_access_key}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        aws_secret_access_key: e.target.value,
                      })
                    }
                  />
                </div>

                {/* Bucket Configuration */}
                <div className="space-y-2">
                  <Label htmlFor="bucket_name">Bucket Name *</Label>
                  <Input
                    id="bucket_name"
                    type="text"
                    placeholder="my-company-airweave-events"
                    value={formData.bucket_name}
                    onChange={(e) =>
                      setFormData({ ...formData, bucket_name: e.target.value })
                    }
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="bucket_prefix">Bucket Prefix</Label>
                    <Input
                      id="bucket_prefix"
                      type="text"
                      placeholder="airweave-outbound/"
                      value={formData.bucket_prefix}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          bucket_prefix: e.target.value,
                        })
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="aws_region">AWS Region</Label>
                    <Input
                      id="aws_region"
                      type="text"
                      placeholder="us-east-1"
                      value={formData.aws_region}
                      onChange={(e) =>
                        setFormData({ ...formData, aws_region: e.target.value })
                      }
                    />
                  </div>
                </div>

                {/* Advanced Options */}
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-muted-foreground hover:text-foreground cursor-pointer text-sm font-medium"
                  >
                    {showAdvanced ? "▼" : "▶"} Advanced Options (MinIO,
                    LocalStack, etc.)
                  </button>
                  {showAdvanced && (
                    <div className="mt-2 space-y-4 pl-4">
                      <div className="space-y-2">
                        <Label htmlFor="endpoint_url">
                          Custom Endpoint URL
                        </Label>
                        <Input
                          id="endpoint_url"
                          type="text"
                          placeholder="http://localhost:9000 (leave empty for AWS S3)"
                          value={formData.endpoint_url}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              endpoint_url: e.target.value,
                            })
                          }
                        />
                        <p className="text-muted-foreground text-xs">
                          For MinIO, LocalStack, or Cloudflare R2. Leave empty
                          for AWS S3.
                        </p>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="use_ssl"
                          checked={formData.use_ssl}
                          onCheckedChange={(checked) =>
                            setFormData({
                              ...formData,
                              use_ssl: checked === true,
                            })
                          }
                        />
                        <Label
                          htmlFor="use_ssl"
                          className="cursor-pointer text-sm"
                        >
                          Use SSL/TLS (recommended for production)
                        </Label>
                      </div>
                    </div>
                  )}
                </div>

                {testResult && !testResult.success && (
                  <Alert variant="destructive">
                    <XCircle className="size-4" />
                    <AlertDescription>{testResult.message}</AlertDescription>
                  </Alert>
                )}
              </div>

              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  onClick={() => testMutation.mutate()}
                  disabled={!isFormValid || testMutation.isPending}
                >
                  {testMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Testing Connection...
                    </>
                  ) : (
                    "Test Connection"
                  )}
                </Button>
              </div>
            </>
          )}

          {step === "testing" && testResult?.success && (
            <>
              <Alert className="border-green-500 bg-green-50 dark:bg-green-950">
                <CheckCircle2 className="size-4 text-green-600" />
                <AlertDescription className="text-green-600">
                  {testResult.message}
                </AlertDescription>
              </Alert>

              <div className="space-y-3 text-sm">
                <p className="font-medium">Configuration Summary:</p>
                <div className="text-muted-foreground space-y-1">
                  <p>• Bucket: {formData.bucket_name}</p>
                  <p>• Region: {formData.aws_region}</p>
                  <p>• Prefix: {formData.bucket_prefix}</p>
                  {formData.endpoint_url && (
                    <p>• Endpoint: {formData.endpoint_url}</p>
                  )}
                </div>
                <p className="text-muted-foreground mt-4">
                  Once configured, all future syncs will automatically write
                  data to both Qdrant (for search) and S3 (for event streaming).
                </p>
              </div>

              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setStep("configure")}>
                  Back to Edit
                </Button>
                <Button
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Configuration"
                  )}
                </Button>
              </div>
            </>
          )}

          {step === "success" && (
            <div className="flex flex-col items-center justify-center space-y-4 py-8">
              <CheckCircle2 className="size-16 text-green-500" />
              <div className="space-y-2 text-center">
                <h3 className="text-lg font-semibold">
                  S3 Destination Configured!
                </h3>
                <p className="text-muted-foreground text-sm">
                  All future syncs will automatically write to S3
                </p>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
