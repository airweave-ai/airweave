import { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, Check, ArrowLeft, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";

interface AddSourceWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete: (connectionId: string) => void;
  shortName: string;
  name: string;
  sourceDetails?: SourceDetails;
}

interface ConfigField {
  name: string;
  title: string;
  description: string;
  type: string;
}

interface SourceDetails {
  name: string;
  description: string;
  short_name: string;
  auth_fields?: {
    fields: ConfigField[];
  };
  auth_type?: string;
}

export const AddSourceWizard = ({
  open,
  onOpenChange,
  onComplete,
  shortName,
  name,
  sourceDetails: passedSourceDetails
}: AddSourceWizardProps) => {
  const [step, setStep] = useState(1);
  const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
  const [config, setConfig] = useState<{ name: string; auth_fields: Record<string, string> }>({
    name: "",
    auth_fields: {}
  });
  const [testing, setTesting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (passedSourceDetails) {
      setSourceDetails(passedSourceDetails);

      if (passedSourceDetails.auth_fields?.fields) {
        const initialConfig: Record<string, string> = {};
        passedSourceDetails.auth_fields.fields.forEach((field: ConfigField) => {
          initialConfig[field.name] = "";
        });
        setConfig({
          name: "",
          auth_fields: initialConfig
        });
      }
    }
  }, [passedSourceDetails]);

  useEffect(() => {
    if (open && !passedSourceDetails) {
      fetchSourceDetails();
    }
  }, [open, shortName, passedSourceDetails]);

  useEffect(() => {
    if (!open) {
      setStep(1);
      setSourceDetails(null);
      setConfig({ name: "", auth_fields: {} });
      setTesting(false);
      setIsLoading(false);
    }
  }, [open]);

  const fetchSourceDetails = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.get(`/sources/detail/${shortName}`);
      if (!response.ok) {
        throw new Error("Failed to fetch source details");
      }
      const data = await response.json();
      setSourceDetails(data);

      if (data.auth_fields?.fields) {
        const initialConfig: Record<string, string> = {};
        data.auth_fields.fields.forEach((field: ConfigField) => {
          initialConfig[field.name] = "";
        });
        setConfig({
          name: "",
          auth_fields: initialConfig
        });
      } else {
        // if there are no config fields for the source, no dialog should open
        onOpenChange(false);
      }
    } catch (error) {
      toast.error("Failed to load source configuration");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTest = async () => {
    try {
      setTesting(true);

      if (sourceDetails?.auth_type?.startsWith('oauth2')) {
        // Store config fields in session storage
        sessionStorage.setItem(`oauth2_config_${shortName}`, JSON.stringify({
          connection_name: config.name,
          auth_fields: config.auth_fields
        }));

        // Return early without making POST request for OAuth2 sources
        toast.success("OAuth2 configuration saved");
        onComplete("oauth2_" + shortName);
        onOpenChange(false);
        return;
      } else if (sourceDetails?.auth_type === "config_class" || sourceDetails?.auth_type === "api_key") {
        console.log("I am going to send the config and try to connect")
        const response = await apiClient.post(
          `/connections/connect/source/${shortName}`,
          config
        );
        if (!response.ok) {
          throw new Error("Failed to create connection");
        }
        const data = await response.json();
        toast.success("Connection created successfully!");
        onComplete(data.id);
        onOpenChange(false);
      } else {
        toast.error(`Having auth configuration for auth type "${sourceDetails?.auth_type || 'unknown'}" is not supported`);
      }
    } catch (error) {
      toast.error("Failed to create connection");
    } finally {
      setTesting(false);
    }
  };

  const totalSteps = 2; // We only need 2 steps for sources: config and review

  const validateConfig = () => {
    if (!config.name.trim()) {
      toast.error("Please enter a name for your connection");
      return false;
    }

    // Validate all required fields from auth_fields
    const missingFields = sourceDetails?.auth_fields?.fields.filter(
      field => !config.auth_fields[field.name]?.trim()
    );

    if (missingFields && missingFields.length > 0) {
      toast.error(`Please fill in: ${missingFields.map(f => f.title).join(", ")}`);
      return false;
    }

    return true;
  };

  const handleBack = () => {
    if (step === 2) {
      setStep(1);
    }
  };

  const handleNext = () => {
    if (step === 1 && validateConfig()) {
      setStep(2);
    }
  };

  // Helper function to get first line of description
  const getFirstLineOfDescription = (description: string) => {
    return description.split('\n')[0];
  };

  const maskSensitiveValue = (value: string) => {
    if (!value) return '';
    return value.slice(0, 6) + '*'.repeat(8);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="relative">
            <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-primary/20">
              <div
                style={{ width: `${(step / totalSteps) * 100}%` }}
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-primary transition-all duration-500"
              />
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {step === 1 && (
            <div className="space-y-6 animate-in slide-in-from-right">
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : sourceDetails ? (
                <>
                  <div className="space-y-2">
                    <h2 className="text-2xl font-bold">Configure {sourceDetails.name}</h2>
                    <p className="text-muted-foreground">
                      {getFirstLineOfDescription(sourceDetails.description)}
                    </p>
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">Connection Name</Label>
                      <Input
                        id="name"
                        value={config.name}
                        onChange={(e) => setConfig({ ...config, name: e.target.value })}
                        placeholder="Enter a name for this connection"
                      />
                    </div>

                    {sourceDetails.auth_fields?.fields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <Label htmlFor={field.name}>
                          {field.title}
                          {field.description && (
                            <span className="text-xs text-muted-foreground ml-2">
                              ({field.description})
                            </span>
                          )}
                        </Label>
                        <Input
                          id={field.name}
                          type={field.type === "string" ? "text" : field.type}
                          value={config.auth_fields[field.name] || ""}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              auth_fields: {
                                ...config.auth_fields,
                                [field.name]: e.target.value
                              }
                            })
                          }
                          placeholder={`Enter ${field.title.toLowerCase()}`}
                        />
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-center text-muted-foreground">
                  Failed to load configuration. Please try again.
                </div>
              )}
            </div>
          )}

          {step === 2 && sourceDetails && (
            <div className="space-y-6 animate-in slide-in-from-right">
              <div className="space-y-2">
                <h2 className="text-2xl font-bold">Review Configuration</h2>
                <p className="text-muted-foreground">
                  Review your configuration and test the connection.
                </p>
              </div>
              <div className="space-y-4 rounded-lg border p-4">
                <div className="grid gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Connection Name</p>
                    <p className="font-medium">{config.name}</p>
                  </div>
                  {sourceDetails.auth_fields?.fields.map((field) => (
                    <div key={field.name}>
                      <p className="text-sm text-muted-foreground">{field.title}</p>
                      <p className="font-medium">
                        {field.type === "password" || field.name.toLowerCase().includes('key') || field.name.toLowerCase().includes('token')
                          ? maskSensitiveValue(config.auth_fields[field.name])
                          : config.auth_fields[field.name]}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-between mt-8">
          {step > 1 && (
            <Button variant="outline" onClick={handleBack}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Back
            </Button>
          )}
          {step === 1 ? (
            <Button
              className="ml-auto"
              onClick={handleNext}
              disabled={isLoading}
            >
              Next <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button
              className="ml-auto"
              onClick={handleTest}
              disabled={testing}
            >
              {testing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing Connection
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Complete Setup
                </>
              )}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
