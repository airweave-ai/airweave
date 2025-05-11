import { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, Check, ArrowLeft, ArrowRight } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AdvancedVectorSettings } from "./AdvancedVectorSettings";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";
import { getDestinationIconUrl } from "@/lib/utils/icons";

interface AddDestinationWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete: (shortName: string) => void;
}

interface ConfigField {
  name: string;
  title: string;
  description: string;
  type: string;
}

interface DestinationDetails {
  name: string;
  description: string;
  short_name: string;
  auth_fields?: {
    fields: ConfigField[];
  };
}

interface DestinationConfig {
  name: string;
  auth_fields: Record<string, string>;
}

// We'll fetch this list from the /destinations/list endpoint in practice
const vectorDatabases = [
  {
    id: "pinecone",
    title: "Pinecone",
    description: "Serverless vector database with automatic scaling",
    shortName: "pinecone",
  },
  {
    id: "weaviate",
    title: "Weaviate Cloud",
    description: "Open-source vector search engine",
    shortName: "weaviate",
  },
  {
    id: "milvus",
    title: "Milvus",
    description: "Open-source vector database for scalable similarity search",
    shortName: "milvus",
  },
];

export const AddDestinationWizard = ({ open, onOpenChange, onComplete }: AddDestinationWizardProps) => {
  const [step, setStep] = useState(1);
  const [selectedDB, setSelectedDB] = useState<string | null>(null);
  const [destinationDetails, setDestinationDetails] = useState<DestinationDetails | null>(null);
  const [config, setConfig] = useState<DestinationConfig>({
    name: "",
    auth_fields: {}
  });
  const [testing, setTesting] = useState(false);
  const [activeTab, setActiveTab] = useState("basic");
  const [isLoading, setIsLoading] = useState(false);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setStep(1);
      setSelectedDB(null);
      setDestinationDetails(null);
      setConfig({ name: "", auth_fields: {} });
      setTesting(false);
      setIsLoading(false);
    }
  }, [open]);

  const totalSteps = 3;
  const selectedDbInfo = vectorDatabases.find((db) => db.id === selectedDB);

  const handleDBSelect = async (dbId: string) => {
    try {
      const selectedInfo = vectorDatabases.find(db => db.id === dbId);
      if (!selectedInfo) return;

      setSelectedDB(dbId);
      setIsLoading(true);

      const response = await apiClient.get(`/destinations/detail/${selectedInfo.shortName}`);
      if (!response.ok) {
        throw new Error("Failed to fetch destination details");
      }
      const data = await response.json();

      setDestinationDetails(data);
      if (data.auth_fields?.fields) {
        const initialConfig: Record<string, string> = {};
        data.auth_fields.fields.forEach(field => {
          initialConfig[field.name] = "";
        });
        setConfig({
          name: "",
          auth_fields: initialConfig
        });
      }
      setStep(2);
    } catch (error) {
      toast.error("Failed to load destination configuration");
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    if (step === 2) {
      setStep(1);
      setActiveTab("basic");
      setSelectedDB(null);
      setDestinationDetails(null);
    } else if (step === 3) {
      setStep(2);
    }
  };

  const validateConfig = () => {
    if (!config.name.trim()) {
      toast.error("Please enter a name for your database");
      return false;
    }

    // Validate all required fields from auth_fields
    const missingFields = destinationDetails?.auth_fields?.fields.filter(
      field => !config.auth_fields[field.name]?.trim()
    );

    if (missingFields && missingFields.length > 0) {
      toast.error(`Please fill in: ${missingFields.map(f => f.title).join(", ")}`);
      return false;
    }

    return true;
  };

  const handleNext = () => {
    if (step === 2 && validateConfig()) {
      setStep(3);
    }
  };

  const handleTest = async () => {
    if (!selectedDbInfo) return;

    try {
      setTesting(true);
      const payload = {
        name: config.name,
        auth_fields: config.auth_fields
      };

      await apiClient.post(
        `/connections/connect/destination/${selectedDbInfo.shortName}`,
        payload
      );

      toast.success("Connection test successful!");
      onComplete(selectedDbInfo.shortName);
      onOpenChange(false);
    } catch (error) {
      toast.error("Failed to connect. Please check your settings.");
    } finally {
      setTesting(false);
    }
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
            <div className="space-y-4 animate-in slide-in-from-right">
              <div className="space-y-2">
                <h2 className="text-2xl font-bold">Choose Vector Database</h2>
                <p className="text-muted-foreground">
                  Select which vector database you want to connect.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {vectorDatabases.map((db) => (
                  <Card
                    key={db.id}
                    className={`relative overflow-hidden cursor-pointer transition-all hover:shadow-lg ${selectedDB === db.id ? "ring-2 ring-primary" : ""
                      }`}
                    onClick={() => handleDBSelect(db.id)}
                  >
                    <CardHeader>
                      <div className="flex items-center space-x-4">
                        <img
                          src={getDestinationIconUrl(db.shortName)}
                          alt={`${db.title} icon`}
                          className="w-8 h-8"
                        />
                        <div>
                          <CardTitle>{db.title}</CardTitle>
                          <CardDescription>{db.description}</CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-in slide-in-from-right">
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : destinationDetails ? (
                <>
                  <div className="space-y-2">
                    <h2 className="text-2xl font-bold">Configure {destinationDetails.name}</h2>
                    <p className="text-muted-foreground">{destinationDetails.description}</p>
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
                      <p className="text-sm text-muted-foreground">
                        A friendly name to identify this connection
                      </p>
                    </div>

                    {destinationDetails.auth_fields?.fields.map((field) => (
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

          {step === 3 && destinationDetails && (
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
                  {destinationDetails.auth_fields?.fields.map((field) => (
                    <div key={field.name}>
                      <p className="text-sm text-muted-foreground">{field.title}</p>
                      <p className="font-medium">
                        {field.type === "string" ? "••••••••" : config.auth_fields[field.name]}
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
          {step < 3 ? (
            <Button className="ml-auto" onClick={handleNext} disabled={isLoading}>
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
