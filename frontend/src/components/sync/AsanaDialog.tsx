import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { ExternalLink, LogIn, Building2, CheckCircle2 } from "lucide-react";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

interface AsanaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete?: (connectionId: string) => void;
  shortName: string;
  name: string;
  connections?: any[]; // Accept connections prop
}

export function AsanaDialog({
  open,
  onOpenChange,
  onComplete,
  shortName,
  name,
  connections = []
}: AsanaDialogProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [pat, setPat] = useState("");
  const [connectionName, setConnectionName] = useState("Asana Workspace");
  const { toast } = useToast();
  const { resolvedTheme } = useTheme();

  // Remove auto-proceed timer

  const handleOAuthLogin = () => {
    setIsLoading(true);
    setTimeout(() => {
      if (onComplete) {
        const connectionId = connections && connections.length > 0
          ? connections[0].id
          : `asana-personal-${Date.now()}`;
        onComplete(connectionId);
        onOpenChange(false);
      }
      setIsLoading(false);
    }, 800); // Show loading state briefly
  };

  const handlePATSubmit = () => {
    if (!pat.trim()) {
      toast({
        variant: "destructive",
        title: "Missing Personal Access Token",
        description: "Please enter your Asana PAT",
      });
      return;
    }

    setIsLoading(true);
    setTimeout(() => {
      if (onComplete) {
        const connectionId = connections && connections.length > 0
          ? connections[0].id
          : `asana-workspace-${Date.now()}`;
        onComplete(connectionId);
        onOpenChange(false);
      }
      setIsLoading(false);
    }, 800); // Show loading state briefly
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader className="flex flex-col items-center text-center">
          <div className="w-16 h-16 mb-4 flex items-center justify-center">
            <img
              src={getAppIconUrl("asana", resolvedTheme)}
              alt="Asana logo"
              className="w-12 h-12"
            />
          </div>
          <DialogTitle className="text-xl">Connect to Asana</DialogTitle>
          <DialogDescription className="text-center max-w-sm mx-auto mt-1">
            Choose how you want to connect to your Asana account
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="personal" className="mt-6">
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="personal">Personal Connection</TabsTrigger>
            <TabsTrigger value="workspace">Workspace Connection</TabsTrigger>
          </TabsList>

          <TabsContent value="personal" className="space-y-4">
            <div className="bg-accent/50 p-5 rounded-lg border border-accent shadow-sm">
              <div className="flex items-start space-x-4">
                <div className="bg-blue-100 dark:bg-blue-900/30 p-2 rounded-full">
                  <LogIn className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="font-medium text-base">Personal OAuth Connection</h3>
                  <p className="text-sm text-muted-foreground mt-1.5">
                    Connect with your personal Asana account using OAuth. This provides access to your personal tasks and projects.
                  </p>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Quick setup with just a few clicks</span>
                </div>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Access to your personal tasks and workspaces</span>
                </div>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Secure authentication via Asana</span>
                </div>
              </div>

              <Button
                className="w-full mt-5"
                onClick={handleOAuthLogin}
                disabled={isLoading}
              >
                {isLoading ? "Connecting..." : "Connect with Asana"}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="workspace" className="space-y-4">
            <div className="bg-accent/50 p-5 rounded-lg border border-accent shadow-sm">
              <div className="flex items-start space-x-4">
                <div className="bg-purple-100 dark:bg-purple-900/30 p-2 rounded-full">
                  <Building2 className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-medium text-base">Workspace Connection</h3>
                  <p className="text-sm text-muted-foreground mt-1.5">
                    Connect to your Asana workspace using a Personal Access Token (PAT). This provides broader access to the entire workspace.
                  </p>

                  <div className="mt-3">
                    <a
                      href="https://docs.airweave.ai"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 dark:text-blue-400 flex items-center hover:underline"
                    >
                      Learn how to get your PAT
                      <ExternalLink className="h-3 w-3 ml-1" />
                    </a>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Full access to organization data</span>
                </div>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>Access data from all workspace members</span>
                </div>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span>More control over access permissions</span>
                </div>
              </div>

              <div className="space-y-3 mt-5">
                <div className="space-y-2">
                  <Label htmlFor="connection-name">Connection Name</Label>
                  <Input
                    id="connection-name"
                    placeholder="My Asana Workspace"
                    value={connectionName}
                    onChange={(e) => setConnectionName(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="pat">Personal Access Token</Label>
                  <Input
                    id="pat"
                    placeholder="Enter your Asana PAT"
                    type="password"
                    value={pat}
                    onChange={(e) => setPat(e.target.value)}
                  />
                </div>

                <Button
                  className="w-full"
                  onClick={handlePATSubmit}
                  disabled={isLoading}
                >
                  {isLoading ? "Connecting..." : "Connect with PAT"}
                </Button>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
