import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Link as LinkIcon,
  Trash2,
  Info,
  Code,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { ModelSettings } from "./types";
import { Badge } from "@/components/ui/badge";
import { getAppIconUrl, getDestinationIconUrl } from "@/lib/utils/icons";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChatInfoSidebarProps } from "./types";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";
import { ApiReferenceDialog } from "./ApiReferenceDialog";

// Default model to use if none is selected
const DEFAULT_MODEL = "claude-3-7-sonnet-20250219";

const AVAILABLE_MODELS = [
  { id: "claude-3-7-sonnet-20250219", name: "Claude 3.7 Sonnet" },
  { id: "claude-3-5-sonnet-20241022", name: "Claude 3.5 Sonnet" },
  { id: "claude-3-opus-20240229", name: "Claude 3 Opus" },
  { id: "claude-3-sonnet-20240229", name: "Claude 3 Sonnet" },
  { id: "claude-3-haiku-20240307", name: "Claude 3 Haiku" },
  { id: "gpt-4o", name: "GPT-4o" },
  { id: "gpt-4o-mini", name: "GPT-4o Mini" },
  { id: "o1-preview", name: "O1 Preview" },
];

// Add this custom badge style variant
const badgeVariants = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  inactive: "bg-gray-50 text-gray-600 border-gray-200",
};


export function ChatInfoSidebar({ chatInfo, onUpdateSettings }: ChatInfoSidebarProps) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  
  // Stable references for state management
  const initialSettingsRef = useRef(chatInfo.model_settings);
  const initialModelRef = useRef(chatInfo.model_name || DEFAULT_MODEL);
  
  // State for UI
  const [modelSettings, setModelSettings] = useState<ModelSettings>(initialSettingsRef.current);
  const [modelName, setModelName] = useState<string>(initialModelRef.current);
  const [lastUserMessage, setLastUserMessage] = useState<string>("Your search query here");
  const [saveTimeout, setSaveTimeout] = useState<NodeJS.Timeout | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showApiDialog, setShowApiDialog] = useState(false);
  const [isModelUpdating, setIsModelUpdating] = useState(false);
  
  // Prevent unwanted updates from props during local changes
  const ignorePropsUpdatesRef = useRef(false);
  
  // When the component mounts, log the initial state
  useEffect(() => {
    console.log("Initial model:", initialModelRef.current);
    console.log("ChatInfo model:", chatInfo.model_name);
    
    if (!chatInfo.model_name) {
      // If no model is provided, set the default model in backend
      void handleModelChange(DEFAULT_MODEL, true);
    }
    
    // Get the last user message from the chat
    void getLastUserMessage();
  }, []);
  
  // Update state when chatInfo changes, unless we're in the middle of an update
  useEffect(() => {
    if (ignorePropsUpdatesRef.current) {
      return;
    }
    
    const newModelName = chatInfo.model_name || DEFAULT_MODEL;
    
    // Only update if the model has actually changed
    if (modelName !== newModelName) {
      console.log("Updating model from props:", newModelName);
      setModelName(newModelName);
    }
    
    setModelSettings(chatInfo.model_settings);
  }, [chatInfo.model_name, chatInfo.model_settings]);

  // Fetch the last user message
  const getLastUserMessage = async () => {
    try {
      const response = await apiClient.get(`/chat/${chatInfo.id}`);
      const chatData = await response.json();

      if (chatData.messages && chatData.messages.length > 0) {
        // Find the last user message
        const userMessages = chatData.messages.filter((msg: any) => msg.role === "user");
        if (userMessages.length > 0) {
          setLastUserMessage(userMessages[userMessages.length - 1].content);
        }
      }
    } catch (error) {
      console.error("Failed to fetch last user message:", error);
    }
  };

  const handleModelChange = async (newModelName: string, isInitial = false) => {
    if (newModelName === modelName && !isInitial) {
      return; // No change, nothing to do
    }
    
    // Set flag to ignore props updates during API call
    setIsModelUpdating(true);
    ignorePropsUpdatesRef.current = true;
    
    // Update local state immediately
    setModelName(newModelName);
    
    try {
      // Update model on the server
      await onUpdateSettings({ model_name: newModelName } as any);
      
      if (!isInitial) {
        const modelDisplayName = AVAILABLE_MODELS.find(m => m.id === newModelName)?.name || newModelName;
        toast({
          title: "Model updated",
          description: `Changed to ${modelDisplayName}`,
        });
      }
    } catch (error) {
      // On error, revert to the previous model
      console.error("Failed to update model:", error);
      setModelName(chatInfo.model_name || DEFAULT_MODEL);
      
      if (!isInitial) {
        toast({
          title: "Error",
          description: "Failed to update model. Please try again.",
          variant: "destructive",
        });
      }
    } finally {
      // Reset flags after a short delay to ensure any incoming prop updates don't cause issues
      setTimeout(() => {
        setIsModelUpdating(false);
        ignorePropsUpdatesRef.current = false;
      }, 300);
    }
  };

  const handleSettingChange = (key: keyof ModelSettings, value: number | string) => {
    // Create new settings object with the updated value
    const newSettings = { ...modelSettings, [key]: value };
    setModelSettings(newSettings);

    // Clear existing timeout
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }

    // For other settings, use debounce
    const timeout = setTimeout(async () => {
      try {
        // Update model_settings separately
        await onUpdateSettings({ model_settings: newSettings } as any);
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to save settings",
          variant: "destructive",
        });
      }
    }, 500);

    setSaveTimeout(timeout);
  };

  const handleDelete = async () => {
    try {
      await apiClient.delete(`/chat/${chatInfo.id}`);
      toast({
        title: "Chat deleted",
        description: "The chat has been deleted successfully.",
      });
      navigate('/chat');
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete chat",
        variant: "destructive",
      });
    }
  };

  // Get display name for current model
  const currentModelName = AVAILABLE_MODELS.find(m => m.id === modelName)?.name || "Select a model";

  return (
    <>
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Chat</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this chat? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setShowDeleteDialog(false);
                void handleDelete();
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Use the ApiReferenceDialog component */}
      <ApiReferenceDialog
        open={showApiDialog}
        onOpenChange={setShowApiDialog}
        modelName={modelName}
        modelSettings={modelSettings}
        syncId={chatInfo.sync_id}
        lastUserMessage={lastUserMessage}
      />

      <div className="w-[350px] border-l bg-background">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold">Chat Settings</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowApiDialog(true)}
              className="h-8 w-8 text-muted-foreground hover:text-primary border border-border/20 rounded-md"
              title="API Reference"
            >
              <Code className="h-8 w-8" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowDeleteDialog(true)}
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-6 w-6" />
            </Button>
          </div>
        </div>

        <ScrollArea className="h-[calc(100vh-65px)]">
          <div className="p-4 space-y-6">

            {/* Chat Details Section */}
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-muted-foreground">CHAT DETAILS</h3>
                <div className="rounded-lg border p-3 space-y-3">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Name</Label>
                    <p className="text-sm font-medium">{chatInfo.name}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Chat ID</Label>
                    <p className="text-xs font-mono text-muted-foreground">{chatInfo.id}</p>
                  </div>
                  {chatInfo.description && (
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Description</Label>
                      <p className="text-sm">{chatInfo.description}</p>
                    </div>
                  )}
                </div>
              </div>


              {/* Data Connection Section */}
              {chatInfo.sync && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-muted-foreground">DATA CONNECTION</h3>
                  <div className="rounded-lg border p-3 space-y-4">
                    {/* Sync Details */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{chatInfo.sync.name}</span>
                        <Badge
                          className={cn(
                            "text-[10px] font-medium px-2 py-0.5 border",
                            chatInfo.sync.status === 'active' ? badgeVariants.active : badgeVariants.inactive
                          )}
                        >
                          {chatInfo.sync.status}
                        </Badge>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Sync ID</Label>
                        <p className="text-xs font-mono text-muted-foreground">{chatInfo.sync.id}</p>
                      </div>
                    </div>

                    <Separator />

                    {/* Source Connection */}
                    {chatInfo.sync.source_connection && (
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">Source</Label>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <img
                                src={getAppIconUrl(chatInfo.sync.source_connection.short_name, resolvedTheme)}
                                alt={chatInfo.sync.source_connection.source?.name}
                                className="h-5 w-5"
                              />
                              <span className="text-sm">{chatInfo.sync.source_connection.source?.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {chatInfo.sync.source_connection.source?.app_url && (
                                <a
                                  href={chatInfo.sync.source_connection.source.app_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-muted-foreground hover:text-primary"
                                >
                                  <LinkIcon className="h-3 w-3" />
                                </a>
                              )}
                              <Badge
                                className={cn(
                                  "text-[10px] font-medium px-2 py-0.5 border",
                                  chatInfo.sync.source_connection.status === 'active' ? badgeVariants.active : badgeVariants.inactive
                                )}
                              >
                                {chatInfo.sync.source_connection.status}
                              </Badge>
                            </div>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">Connection ID</Label>
                            <p className="text-xs font-mono text-muted-foreground">{chatInfo.sync.source_connection.id}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    <Separator />

                    {/* Destination */}
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Destination</Label>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <img
                            src={getDestinationIconUrl(
                              chatInfo.sync.destination_connection?.short_name || "qdrant"
                            )}
                            alt={chatInfo.sync.destination_connection?.destination?.name || "Qdrant"}
                            className="h-5 w-5"
                          />
                          <span className="text-sm">
                            {chatInfo.sync.destination_connection?.destination?.name || "Native Qdrant"}
                          </span>
                        </div>
                        {chatInfo.sync.destination_connection && (
                          <>
                            <div className="space-y-1">
                              <Label className="text-xs text-muted-foreground">Connection ID</Label>
                              <p className="text-xs font-mono text-muted-foreground">{chatInfo.sync.destination_connection.id}</p>
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs text-muted-foreground">Status</Label>
                              <Badge
                                className={cn(
                                  "text-[10px] font-medium px-2 py-0.5 border",
                                  chatInfo.sync.destination_connection.status === 'active' ? badgeVariants.active : badgeVariants.inactive
                                )}
                              >
                                {chatInfo.sync.destination_connection.status}
                              </Badge>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Model Settings Section */}
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-muted-foreground">MODEL SETTINGS</h3>
                <div className="rounded-lg border p-3 space-y-4">
                  {/* Model Selection */}
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Model</Label>
                    <Select
                      value={modelName}
                      onValueChange={(value) => void handleModelChange(value)}
                      defaultValue={DEFAULT_MODEL}
                      disabled={isModelUpdating}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model">
                          {currentModelName}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {AVAILABLE_MODELS.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {isModelUpdating && (
                      <p className="text-xs text-muted-foreground">Updating model...</p>
                    )}
                  </div>

                  {/* Temperature */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Temperature</Label>
                      <span className="text-xs">{modelSettings.temperature?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.temperature ?? 0.7]}
                      min={0}
                      max={1}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("temperature", value)}
                    />
                  </div>

                  {/* Max Tokens */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Max Tokens</Label>
                      <span className="text-xs">{modelSettings.max_tokens}</span>
                    </div>
                    <Slider
                      value={[modelSettings.max_tokens ?? 1000]}
                      min={100}
                      max={4000}
                      step={100}
                      onValueChange={([value]) => handleSettingChange("max_tokens", value)}
                    />
                  </div>

                  {/* Top P */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Top P</Label>
                      <span className="text-xs">{modelSettings.top_p?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.top_p ?? 1]}
                      min={0}
                      max={1}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("top_p", value)}
                    />
                  </div>

                  {/* Frequency Penalty */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Frequency Penalty</Label>
                      <span className="text-xs">{modelSettings.frequency_penalty?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.frequency_penalty ?? 0]}
                      min={0}
                      max={2}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("frequency_penalty", value)}
                    />
                  </div>

                  {/* Presence Penalty */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Presence Penalty</Label>
                      <span className="text-xs">{modelSettings.presence_penalty?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.presence_penalty ?? 0]}
                      min={0}
                      max={2}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("presence_penalty", value)}
                    />
                  </div>
                </div>
              </div>

            </div>
          </div>
        </ScrollArea>
      </div>
    </>
  );
}
