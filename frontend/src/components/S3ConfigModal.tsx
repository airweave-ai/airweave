import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, XCircle, CloudUpload, Info, Copy, Check, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';

interface S3ConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface S3Config {
  role_arn: string;
  external_id: string;
  bucket_name: string;
  bucket_prefix: string;
  aws_region: string;
}

type Step = 'setup-instructions' | 'configure' | 'testing' | 'success';

export function S3ConfigModal({ isOpen, onClose, onSuccess }: S3ConfigModalProps) {
  const [step, setStep] = useState<Step>('setup-instructions');
  const [isLoading, setIsLoading] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Generate a unique external ID for this organization
  // AWS external IDs must match: [\w+=,.@:\/-]*
  const [generatedExternalId] = useState(() => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = 'airweave-';
    for (let i = 0; i < 32; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  });

  const [config, setConfig] = useState<S3Config>({
    role_arn: '',
    external_id: generatedExternalId,
    bucket_name: '',
    bucket_prefix: 'airweave/',
    aws_region: 'us-east-1',
  });

  const handleCopy = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleTestConnection = async () => {
    setIsLoading(true);
    setTestResult(null);

    try {
      const response = await apiClient.post('/s3/test', config);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Connection test failed');
      }

      const result = await response.json();
      setTestResult({ success: true, message: result.message });
      setStep('testing');
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.message || 'Failed to connect to S3',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveConfiguration = async () => {
    setIsLoading(true);

    try {
      const response = await apiClient.post('/s3/configure', config);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save configuration');
      }

      setStep('success');
      toast.success('S3 destination configured successfully');

      // Call onSuccess callback after short delay
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 2000);
    } catch (error: any) {
      toast.error(error.message || 'Failed to save S3 configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setStep('setup-instructions');
    setTestResult(null);
    onClose();
  };

  const isFormValid = () => {
    return (
      config.role_arn.trim() !== '' &&
      config.role_arn.startsWith('arn:aws:iam::') &&
      config.external_id.trim() !== '' &&
      config.bucket_name.trim() !== ''
    );
  };

  // Airweave's AWS account ID for cross-account trust policy
  // Dev: 050451371276, Prd: 238479992525
  const airweaveAwsAccountId = import.meta.env.VITE_AWS_ACCOUNT_ID || '238479992525';

  const trustPolicyJson = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Principal: { AWS: `arn:aws:iam::${airweaveAwsAccountId}:root` },
      Action: 'sts:AssumeRole',
      Condition: {
        StringEquals: { 'sts:ExternalId': config.external_id }
      }
    }]
  }, null, 2);

  const s3PolicyJson = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Action: ['s3:PutObject', 's3:GetObject', 's3:DeleteObject', 's3:ListBucket'],
      Resource: [
        `arn:aws:s3:::${config.bucket_name || 'YOUR-BUCKET-NAME'}`,
        `arn:aws:s3:::${config.bucket_name || 'YOUR-BUCKET-NAME'}/${config.bucket_prefix}*`
      ]
    }]
  }, null, 2);

  // Step indicator component
  const StepIndicator = ({ number, title }: { number: number; title: string }) => (
    <div className="flex items-center gap-3 mb-3">
      <div className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 dark:bg-primary/20 text-primary text-xs font-semibold">
        {number}
      </div>
      <h3 className="font-medium text-sm text-foreground">{title}</h3>
    </div>
  );

  // Code block component with integrated copy button
  const CodeBlock = ({ code, fieldName }: { code: string; fieldName: string }) => (
    <div className="relative group rounded-xl overflow-hidden border border-border/50 dark:border-border/30">
      <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-slate-800/80 to-transparent dark:from-slate-900/80 pointer-events-none" />
      <pre className="bg-slate-900/95 dark:bg-slate-950 text-slate-100 p-4 pt-3 text-xs overflow-x-auto font-mono leading-relaxed">
        {code}
      </pre>
      <Button
        variant="ghost"
        size="sm"
        className={cn(
          "absolute top-2 right-2 h-7 w-7 p-0",
          "bg-slate-700/60 hover:bg-slate-600/80 border border-slate-600/50",
          "text-slate-300 hover:text-white",
          "transition-all duration-200",
          copiedField === fieldName && "bg-emerald-600/80 hover:bg-emerald-600/80 border-emerald-500/50"
        )}
        onClick={() => handleCopy(code, fieldName)}
      >
        {copiedField === fieldName ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
    </div>
  );

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto border-border/50 dark:border-border/30 shadow-xl dark:shadow-2xl dark:shadow-black/20">
        <DialogHeader className="pb-2">
          <DialogTitle className="flex items-center gap-2.5 text-lg">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 dark:bg-primary/20">
              <CloudUpload className="h-4 w-4 text-primary" />
            </div>
            Configure S3 Destination
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Set up cross-account access to write data to your S3 bucket
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 pt-2">
          {step === 'setup-instructions' && (
            <>
              <div className="rounded-xl bg-sky-50/80 dark:bg-sky-950/30 border border-sky-200/60 dark:border-sky-800/40 p-4">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    <Info className="h-4 w-4 text-sky-600 dark:text-sky-400" />
                  </div>
                  <p className="text-sm text-sky-800 dark:text-sky-200/90 leading-relaxed">
                    Airweave uses IAM role assumption for secure cross-account access. Follow these
                    steps to set up access to your S3 bucket.
                  </p>
                </div>
              </div>

              <div className="space-y-6">
                {/* Step 1: Bucket Name */}
                <div className="space-y-3">
                  <StepIndicator number={1} title="Enter your S3 bucket details" />
                  <div className="grid grid-cols-2 gap-4 pl-9">
                    <div className="space-y-2">
                      <Label htmlFor="bucket_name_setup" className="text-xs font-medium text-muted-foreground">
                        Bucket Name <span className="text-primary">*</span>
                      </Label>
                      <Input
                        id="bucket_name_setup"
                        type="text"
                        placeholder="my-company-data"
                        value={config.bucket_name}
                        onChange={(e) => setConfig({ ...config, bucket_name: e.target.value })}
                        className="h-9 rounded-lg border-border/60 dark:border-border/40 bg-background dark:bg-muted/30 focus:border-primary/50 focus:ring-primary/20 transition-colors"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="bucket_prefix_setup" className="text-xs font-medium text-muted-foreground">
                        Bucket Prefix
                      </Label>
                      <Input
                        id="bucket_prefix_setup"
                        type="text"
                        placeholder="airweave/"
                        value={config.bucket_prefix}
                        onChange={(e) => setConfig({ ...config, bucket_prefix: e.target.value })}
                        className="h-9 rounded-lg border-border/60 dark:border-border/40 bg-background dark:bg-muted/30 focus:border-primary/50 focus:ring-primary/20 transition-colors"
                      />
                    </div>
                  </div>
                </div>

                {/* Step 2: External ID */}
                <div className="space-y-3">
                  <StepIndicator number={2} title="Use this External ID in your trust policy" />
                  <div className="flex items-center gap-2 pl-9">
                    <Input
                      value={config.external_id}
                      readOnly
                      className="h-9 font-mono text-sm rounded-lg bg-muted/50 dark:bg-muted/30 border-border/60 dark:border-border/40 text-foreground/80"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      className={cn(
                        "h-9 px-3 rounded-lg border-border/60 dark:border-border/40 transition-all duration-200",
                        copiedField === 'external_id'
                          ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-700 text-emerald-600 dark:text-emerald-400"
                          : "hover:bg-muted/50 dark:hover:bg-muted/30"
                      )}
                      onClick={() => handleCopy(config.external_id, 'external_id')}
                    >
                      {copiedField === 'external_id' ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Step 3: Create IAM Role */}
                <div className="space-y-3">
                  <StepIndicator number={3} title="Create IAM Role in your AWS account" />
                  <div className="pl-9 space-y-3">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Create a new IAM role with the following trust policy (allows Airweave to assume the role):
                    </p>
                    <CodeBlock code={trustPolicyJson} fieldName="trust_policy" />
                  </div>
                </div>

                {/* Step 4: Attach S3 Policy */}
                <div className="space-y-3">
                  <StepIndicator number={4} title="Attach S3 permissions to the role" />
                  <div className="pl-9 space-y-3">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Attach this inline policy or create a custom policy with these permissions:
                    </p>
                    <CodeBlock code={s3PolicyJson} fieldName="s3_policy" />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2 border-t border-border/40 dark:border-border/20">
                <Button
                  variant="outline"
                  onClick={handleClose}
                  className="h-9 px-4 rounded-lg border-border/60 dark:border-border/40 hover:bg-muted/50 dark:hover:bg-muted/30 transition-colors"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => setStep('configure')}
                  disabled={!config.bucket_name.trim()}
                  className={cn(
                    "h-9 px-4 rounded-lg transition-all duration-200",
                    "bg-primary hover:bg-primary/90 text-primary-foreground",
                    !config.bucket_name.trim() && "opacity-50 cursor-not-allowed"
                  )}
                >
                  Continue to Configuration
                  <ChevronRight className="ml-1.5 h-4 w-4" />
                </Button>
              </div>
            </>
          )}

          {step === 'configure' && (
            <>
              <div className="space-y-5">
                {/* Role ARN */}
                <div className="space-y-2">
                  <Label htmlFor="role_arn" className="text-sm font-medium">
                    IAM Role ARN <span className="text-primary">*</span>
                  </Label>
                  <Input
                    id="role_arn"
                    type="text"
                    placeholder="arn:aws:iam::123456789012:role/airweave-writer"
                    value={config.role_arn}
                    onChange={(e) => setConfig({ ...config, role_arn: e.target.value })}
                    className="h-10 rounded-lg border-border/60 dark:border-border/40 bg-background dark:bg-muted/30 focus:border-primary/50 focus:ring-primary/20 transition-colors font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    The ARN of the IAM role you created in your AWS account
                  </p>
                </div>

                {/* External ID (read-only) */}
                <div className="space-y-2">
                  <Label htmlFor="external_id" className="text-sm font-medium">External ID</Label>
                  <Input
                    id="external_id"
                    type="text"
                    value={config.external_id}
                    readOnly
                    className="h-10 rounded-lg bg-muted/50 dark:bg-muted/30 border-border/60 dark:border-border/40 text-foreground/80 font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    This must match the external ID in your role's trust policy
                  </p>
                </div>

                {/* Bucket Configuration */}
                <div className="space-y-2">
                  <Label htmlFor="bucket_name" className="text-sm font-medium">
                    Bucket Name <span className="text-primary">*</span>
                  </Label>
                  <Input
                    id="bucket_name"
                    type="text"
                    placeholder="my-company-airweave-data"
                    value={config.bucket_name}
                    onChange={(e) => setConfig({ ...config, bucket_name: e.target.value })}
                    className="h-10 rounded-lg border-border/60 dark:border-border/40 bg-background dark:bg-muted/30 focus:border-primary/50 focus:ring-primary/20 transition-colors"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="bucket_prefix" className="text-sm font-medium">Bucket Prefix</Label>
                    <Input
                      id="bucket_prefix"
                      type="text"
                      placeholder="airweave/"
                      value={config.bucket_prefix}
                      onChange={(e) => setConfig({ ...config, bucket_prefix: e.target.value })}
                      className="h-10 rounded-lg border-border/60 dark:border-border/40 bg-background dark:bg-muted/30 focus:border-primary/50 focus:ring-primary/20 transition-colors"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="aws_region" className="text-sm font-medium">AWS Region</Label>
                    <Input
                      id="aws_region"
                      type="text"
                      placeholder="us-east-1"
                      value={config.aws_region}
                      onChange={(e) => setConfig({ ...config, aws_region: e.target.value })}
                      className="h-10 rounded-lg border-border/60 dark:border-border/40 bg-background dark:bg-muted/30 focus:border-primary/50 focus:ring-primary/20 transition-colors"
                    />
                  </div>
                </div>

                {testResult && !testResult.success && (
                  <div className="rounded-xl bg-red-50/80 dark:bg-red-950/30 border border-red-200/60 dark:border-red-800/40 p-4">
                    <div className="flex gap-3">
                      <XCircle className="h-4 w-4 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-red-800 dark:text-red-200/90">{testResult.message}</p>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-between gap-3 pt-2 border-t border-border/40 dark:border-border/20">
                <Button
                  variant="ghost"
                  onClick={() => setStep('setup-instructions')}
                  className="h-9 px-4 rounded-lg hover:bg-muted/50 dark:hover:bg-muted/30 text-muted-foreground hover:text-foreground transition-colors"
                >
                  Back to Instructions
                </Button>
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    onClick={handleClose}
                    className="h-9 px-4 rounded-lg border-border/60 dark:border-border/40 hover:bg-muted/50 dark:hover:bg-muted/30 transition-colors"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleTestConnection}
                    disabled={!isFormValid() || isLoading}
                    className={cn(
                      "h-9 px-4 rounded-lg transition-all duration-200",
                      "bg-primary hover:bg-primary/90 text-primary-foreground",
                      (!isFormValid() || isLoading) && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      'Test Connection'
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}

          {step === 'testing' && testResult?.success && (
            <>
              <div className="rounded-xl bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200/60 dark:border-emerald-800/40 p-4">
                <div className="flex gap-3">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-emerald-800 dark:text-emerald-200/90">
                    {testResult.message}
                  </p>
                </div>
              </div>

              <div className="rounded-xl bg-muted/30 dark:bg-muted/20 border border-border/40 dark:border-border/20 p-5 space-y-4">
                <h4 className="font-medium text-sm text-foreground">Configuration Summary</h4>
                <div className="grid gap-3 text-sm">
                  <div className="flex items-start gap-3">
                    <span className="text-muted-foreground w-16 flex-shrink-0">Role</span>
                    <span className="font-mono text-xs text-foreground/80 break-all">{config.role_arn}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-muted-foreground w-16 flex-shrink-0">Bucket</span>
                    <span className="font-mono text-xs text-foreground/80">{config.bucket_name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-muted-foreground w-16 flex-shrink-0">Region</span>
                    <span className="font-mono text-xs text-foreground/80">{config.aws_region}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-muted-foreground w-16 flex-shrink-0">Prefix</span>
                    <span className="font-mono text-xs text-foreground/80">{config.bucket_prefix || '(none)'}</span>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground pt-2 border-t border-border/30">
                  Once configured, all future syncs will automatically write data to both Vespa
                  (for search) and your S3 bucket (in ARF format).
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-2 border-t border-border/40 dark:border-border/20">
                <Button
                  variant="ghost"
                  onClick={() => setStep('configure')}
                  className="h-9 px-4 rounded-lg hover:bg-muted/50 dark:hover:bg-muted/30 text-muted-foreground hover:text-foreground transition-colors"
                >
                  Back to Edit
                </Button>
                <Button
                  onClick={handleSaveConfiguration}
                  disabled={isLoading}
                  className={cn(
                    "h-9 px-5 rounded-lg transition-all duration-200",
                    "bg-emerald-600 hover:bg-emerald-500 text-white",
                    isLoading && "opacity-50 cursor-not-allowed"
                  )}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                      Save Configuration
                    </>
                  )}
                </Button>
              </div>
            </>
          )}

          {step === 'success' && (
            <div className="flex flex-col items-center justify-center py-10 space-y-5">
              <div className="relative">
                <div className="absolute inset-0 bg-emerald-500/20 dark:bg-emerald-400/20 rounded-full blur-xl" />
                <div className="relative flex items-center justify-center w-20 h-20 rounded-full bg-emerald-100 dark:bg-emerald-900/50">
                  <CheckCircle2 className="h-10 w-10 text-emerald-600 dark:text-emerald-400" />
                </div>
              </div>
              <div className="text-center space-y-2">
                <h3 className="text-xl font-semibold text-foreground">S3 Destination Configured!</h3>
                <p className="text-sm text-muted-foreground max-w-xs">
                  All future syncs will automatically write to your S3 bucket
                </p>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
