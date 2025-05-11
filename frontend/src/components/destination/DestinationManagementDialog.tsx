import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, Trash2, Database, Unplug, Code, Clock, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { AdvancedVectorSettings } from "./AdvancedVectorSettings";
import { apiClient } from "@/lib/api";

interface DestinationDetails {
  name: string;
  description: string;
  short_name: string;
  class_name: string;
  auth_type: string;
  auth_config_class: string;
  id: string;
  created_at: string;
  modified_at: string;
  auth_fields: {
    fields: {
      name: string;
      title: string;
      description: string;
      type: string;
    }[];
  };
}

interface DestinationManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connection: {
    id: string;
    name: string;
    short_name: string;
    status: string;
    integration_type: string;
    integration_credential_id: string;
  };
  onDelete: () => void;
}

export function DestinationManagementDialog({
  open,
  onOpenChange,
  connection,
  onDelete,
}: DestinationManagementDialogProps) {
  const [name, setName] = useState(connection.name);
  const [showCredentials, setShowCredentials] = useState<Record<string, boolean>>({});
  const [showDeleteAlert, setShowDeleteAlert] = useState(false);
  const [destinationDetails, setDestinationDetails] = useState<DestinationDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});

  useEffect(() => {
    const fetchDestinationDetails = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get(`/destinations/detail/${connection.short_name}`);
        if (!response.ok) throw new Error("Failed to fetch destination details");
        const data = await response.json();
        setDestinationDetails(data);
      } catch (error) {
        toast.error("Failed to load destination details");
      } finally {
        setIsLoading(false);
      }
    };

    if (open && connection.short_name) {
      fetchDestinationDetails();
    }
  }, [open, connection.short_name]);

  useEffect(() => {
    const fetchCredentials = async () => {
      try {
        const response = await apiClient.get(`/connections/credentials/${connection.id}`);
        if (!response.ok) throw new Error("Failed to fetch credentials");
        const data = await response.json();
        setCredentials(data);
      } catch (error) {
        toast.error("Failed to load credentials");
        console.error(error);
      }
    };

    if (open && connection.id) {
      fetchCredentials();
    }
  }, [open, connection.id]);

  const handleDisconnect = async () => {
    try {
      await apiClient.put(`/connections/disconnect/destination/${connection.id}`);
      toast.success("Connection disconnected successfully");
      onDelete(); // Refresh the connections list
      setShowDeleteAlert(false);
      onOpenChange(false);
    } catch (error) {
      toast.error("Failed to disconnect connection");
    }
  };

  const handleSave = () => {
    toast.success("Changes saved successfully");
    onOpenChange(false);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const handleCopyToClipboard = async (fieldName: string) => {
    try {
      const textToCopy = credentials[fieldName] || '';
      await navigator.clipboard.writeText(textToCopy);
      setCopiedField(fieldName);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (err) {
      toast.error("Failed to copy to clipboard");
    }
  };

  const toggleFieldVisibility = (fieldName: string) => {
    setShowCredentials(prev => ({
      ...prev,
      [fieldName]: !prev[fieldName]
    }));
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <DialogTitle>Manage Destination</DialogTitle>
                <Badge variant={connection.status === "ACTIVE" ? "default" : "secondary"}>
                  {connection.status.toLowerCase()}
                </Badge>
              </div>
            </div>
            <DialogDescription>
              {destinationDetails?.description || `Configure and manage your ${connection.short_name} destination`}
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="general" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="credentials">Credentials</TabsTrigger>
              <TabsTrigger value="metadata">Metadata</TabsTrigger>
            </TabsList>

            <TabsContent value="general" className="space-y-4">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter destination name"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Integration Type</Label>
                  <Input value={connection.integration_type} disabled />
                </div>

                {destinationDetails && (
                  <div className="space-y-2">
                    <Label>Class Name</Label>
                    <Input value={destinationDetails.class_name} disabled />
                    <p className="text-sm text-muted-foreground pt-4">
                      Created {formatDate(destinationDetails.created_at)}
                    </p>
                  </div>
                )}

                <div className="flex justify-end space-x-2">
                  <Button
                    variant="destructive"
                    onClick={() => setShowDeleteAlert(true)}
                    className="w-full sm:w-auto"
                  >
                    <Unplug className="mr-2 h-4 w-4" />
                    Disconnect
                  </Button>
                  <Button onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
                    Close
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="credentials" className="space-y-4">
              <div className="space-y-4">
                {destinationDetails?.auth_fields.fields.map((field) => (
                  <div key={field.name} className="space-y-2">
                    <Label>{field.title}</Label>
                    <p className="text-sm text-muted-foreground">{field.description}</p>
                    <div className="relative">
                      <Input
                        type={showCredentials[field.name] ? "text" : "password"}
                        value={credentials[field.name] || "••••••••"}
                        disabled
                      />
                      <div className="absolute right-2 top-2 flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => toggleFieldVisibility(field.name)}
                        >
                          {showCredentials[field.name] ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => handleCopyToClipboard(field.name)}
                        >
                          {copiedField === field.name ? (
                            <Check className="h-4 w-4 text-green-500" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="metadata" className="space-y-4">
              {destinationDetails && (
                <div className="space-y-4">
                  <div className="grid gap-2">
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-sm text-muted-foreground">Auth Type</span>
                      <span className="text-sm font-medium">{destinationDetails.auth_type}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-sm text-muted-foreground">Auth Config</span>
                      <span className="text-sm font-mono">{destinationDetails.auth_config_class}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-sm text-muted-foreground">Last Modified</span>
                      <span className="text-sm">{formatDate(destinationDetails.modified_at)}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-sm text-muted-foreground">Destination ID</span>
                      <span className="text-sm font-mono">{destinationDetails.id}</span>
                    </div>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <AlertDialog open={showDeleteAlert} onOpenChange={setShowDeleteAlert}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              Disconnect Connection
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to disconnect <span className="font-medium">{connection.name}</span>?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDisconnect}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Disconnect
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
