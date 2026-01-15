import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CloudUpload, Loader2, CheckCircle2, AlertCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import { S3ConfigModal } from './S3ConfigModal';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { FeatureFlags } from '@/lib/constants/feature-flags';

interface S3Status {
  feature_enabled: boolean;
  configured: boolean;
  connection_id?: string;
  bucket_name?: string;
  role_arn?: string;
  status?: string;
  created_at?: string;
  message?: string;
}

export function S3StatusCard() {
  const hasFeature = useOrganizationStore((state) => state.hasFeature(FeatureFlags.S3_DESTINATION));
  const [status, setStatus] = useState<S3Status | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get('/s3/status');
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch S3 status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (hasFeature) {
      fetchStatus();
    }
  }, [hasFeature]);

  const handleDelete = async () => {
    try {
      const response = await apiClient.delete('/s3/configure');
      if (!response.ok) {
        throw new Error('Failed to delete S3 configuration');
      }

      toast.success('S3 configuration removed');
      setShowDeleteConfirm(false);
      fetchStatus();
    } catch (error: any) {
      toast.error(error.message || 'Failed to remove S3 configuration');
    }
  };

  // Don't show if feature not enabled
  if (!hasFeature) {
    return null;
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudUpload className="h-5 w-5" />
            S3 Event Streaming
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-gray-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading S3 configuration...
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
                <CloudUpload className="h-5 w-5 text-blue-500" />
                S3 Event Streaming
              </CardTitle>
              <CardDescription>
                Sync all collections to S3 for real-time event streaming and archival
              </CardDescription>
            </div>
            {status?.configured && (
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Configured
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {!status?.configured ? (
            <>
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  S3 destination is not configured. Set up your S3 bucket to enable event
                  streaming for all collections.
                </AlertDescription>
              </Alert>

              <Button onClick={() => setShowConfigModal(true)} className="w-full">
                <CloudUpload className="mr-2 h-4 w-4" />
                Configure S3 Destination
              </Button>

              <div className="text-xs text-gray-500 space-y-1">
                <p className="font-medium">How it works:</p>
                <ul className="list-disc list-inside space-y-0.5 ml-2">
                  <li>Uses cross-account IAM role for secure access</li>
                  <li>No long-lived credentials stored</li>
                  <li>Writes data in ARF format for easy parsing</li>
                </ul>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Bucket</span>
                  <span className="font-mono font-medium">{status.bucket_name}</span>
                </div>
                {status.role_arn && (
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600 dark:text-gray-400">IAM Role</span>
                    <span className="font-mono text-xs truncate max-w-[200px]" title={status.role_arn}>
                      {status.role_arn}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Status</span>
                  <Badge variant="outline">{status.status || 'ACTIVE'}</Badge>
                </div>
                {status.created_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Configured</span>
                    <span className="text-gray-600">
                      {new Date(status.created_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              <Alert className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800">
                <CheckCircle2 className="h-4 w-4 text-blue-600" />
                <AlertDescription className="text-blue-600 dark:text-blue-400">
                  All syncs automatically write to both Qdrant (search) and S3 (events).
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
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              {showDeleteConfirm && (
                <Alert variant="destructive">
                  <AlertDescription className="space-y-3">
                    <p className="font-medium">Are you sure?</p>
                    <p className="text-sm">
                      This will remove S3 destination. Future syncs will only write to Qdrant.
                      Existing data in S3 will not be deleted.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(false)}
                      >
                        Cancel
                      </Button>
                      <Button variant="destructive" size="sm" onClick={handleDelete}>
                        Yes, Remove S3 Configuration
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <S3ConfigModal
        isOpen={showConfigModal}
        onClose={() => setShowConfigModal(false)}
        onSuccess={fetchStatus}
      />
    </>
  );
}
