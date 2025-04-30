import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Terminal, Copy, Check, Sparkles } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { ModelSettings } from "./types";
import { PythonIcon } from "@/components/icons/PythonIcon";
import { NodeIcon } from "@/components/icons/NodeIcon";
import { McpIcon } from "@/components/icons/McpIcon";
import { CodeBlock } from "@/components/ui/code-block";

interface ApiReferenceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  modelName: string;
  modelSettings: ModelSettings;
  syncId: string;
  lastUserMessage?: string;
}

export function ApiReferenceDialog({
  open,
  onOpenChange,
  modelName,
  modelSettings,
  syncId,
  lastUserMessage = "Your search query here",
}: ApiReferenceDialogProps) {
  const [apiDialogTab, setApiDialogTab] = useState<"rest" | "python" | "node" | "mcp">("rest");
  const { toast } = useToast();

  // Function to build API URLs from settings
  const getApiEndpoints = () => {
    const baseUrl = window.location.origin;
    const apiUrl = `${baseUrl}/search`;

    // Create the cURL command
    const curlSnippet = `curl -G ${apiUrl}/ \\
     -d sync_id="${syncId}" \\
     -d query="${lastUserMessage}"`;

    // Create the Python code
    const pythonSnippet =
`from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
)
client.search.search(
    sync_id="${syncId}",
    query="${lastUserMessage}",
)`;

    // Create the Node.js code
    const nodeSnippet =
`import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });
await client.search.search({
    syncId: "${syncId}",
    query: "${lastUserMessage}"
});`;

    // Create the MCP code (Model Context Protocol)
    const mcpSnippet =
`import { createMCPClient, createLocalServer } from "@modelcontextprotocol/typescript-sdk";

// Initialize an MCP client
const client = await createMCPClient({
  // Use stdio transport for local servers, or WebSocket for remote servers
  transport: {
    type: "stdio",
    command: "node path/to/airweave-mcp-server.js"
  },
  // The current MCP protocol version
  protocolVersion: "2025-03-26"
});

// Connect to the MCP server (which interfaces with Airweave)
await client.initialize();

// Check if the server provides a search tool
const tools = await client.listTools();
const searchTool = tools.find(tool => tool.name === "search");

if (searchTool) {
  // Execute the search using the MCP protocol
  const result = await client.executeTool({
    toolName: "search",
    parameters: {
      syncId: "${syncId}",
      query: "${lastUserMessage}"
    }
  });
  
  console.log("Search results:", result);
  
  // You can also access resources exposed by the server
  const resources = await client.listResources();
  console.log("Available resources:", resources);
}

// Close the connection when done
await client.shutdown();`;

    return {
      curlSnippet,
      pythonSnippet,
      nodeSnippet,
      mcpSnippet
    };
  };

  const docLinkFooter = (
    <div className="text-xs flex items-center gap-2 text-muted-foreground">
      <span>→</span>
      <a href="https://docs.airweave.ai/api-reference/search" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
        Explore the full API documentation
      </a>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Search API Reference</DialogTitle>
          <DialogDescription>
            Use these endpoints to access this search functionality programmatically.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4 max-h-[70vh] overflow-y-auto">
          {/* Tabs - styled like SyncTableView.tsx */}
          <div className="flex space-x-1 p-1 rounded-md mb-4 w-fit">
            <Button
              variant={apiDialogTab === "rest" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("rest")}
              className={cn(
                "rounded-sm text-sm flex items-center gap-2",
                apiDialogTab === "rest"
                  ? "shadow-sm bg-slate-200 dark:bg-muted hover:bg-slate-200 dark:hover:bg-muted hover:text-foreground text-foreground"
                  : "hover:bg-slate-200/60 dark:hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <Terminal className="h-4 w-4" />
              <span>cURL</span>
            </Button>
            <Button
              variant={apiDialogTab === "python" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("python")}
              className={cn(
                "rounded-sm text-sm flex items-center gap-2",
                apiDialogTab === "python"
                  ? "shadow-sm bg-slate-200 dark:bg-muted hover:bg-slate-200 dark:hover:bg-muted hover:text-foreground text-foreground"
                  : "hover:bg-slate-200/60 dark:hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <PythonIcon className="h-4 w-4" />
              <span>Python</span>
            </Button>
            <Button
              variant={apiDialogTab === "node" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("node")}
              className={cn(
                "rounded-sm text-sm flex items-center gap-2",
                apiDialogTab === "node"
                  ? "shadow-sm bg-slate-200 dark:bg-muted hover:bg-slate-200 dark:hover:bg-muted hover:text-foreground text-foreground"
                  : "hover:bg-slate-200/60 dark:hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <NodeIcon className="h-4 w-4" />
              <span>Node.js</span>
            </Button>
            <Button
              variant={apiDialogTab === "mcp" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("mcp")}
              className={cn(
                "rounded-sm text-sm flex items-center gap-2",
                apiDialogTab === "mcp"
                  ? "shadow-sm bg-slate-200 dark:bg-muted hover:bg-slate-200 dark:hover:bg-muted hover:text-foreground text-foreground"
                  : "hover:bg-slate-200/60 dark:hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <McpIcon className="h-4 w-4" />
              <span>MCP</span>
            </Button>
          </div>

          {/* Tab Content */}
          {apiDialogTab === "rest" && (
            <div className="space-y-4">
              <CodeBlock
                code={getApiEndpoints().curlSnippet}
                language="bash"
                badgeText="GET"
                badgeColor="bg-emerald-600 hover:bg-emerald-600"
                title="/search"
                footerContent={docLinkFooter}
              />
            </div>
          )}

          {apiDialogTab === "python" && (
            <div className="space-y-2">
              <CodeBlock
                code={getApiEndpoints().pythonSnippet}
                language="python"
                badgeText="SDK"
                badgeColor="bg-blue-600 hover:bg-blue-600"
                title="AirweaveSDK"
                footerContent={docLinkFooter}
              />
            </div>
          )}

          {apiDialogTab === "node" && (
            <div className="space-y-2">
              <CodeBlock
                code={getApiEndpoints().nodeSnippet}
                language="javascript"
                badgeText="SDK"
                badgeColor="bg-blue-600 hover:bg-blue-600"
                title="AirweaveSDKClient"
                footerContent={docLinkFooter}
              />
            </div>
          )}

          {apiDialogTab === "mcp" && (
            <div className="space-y-2">
              <CodeBlock
                code={getApiEndpoints().mcpSnippet}
                language="javascript"
                badgeText="SDK"
                badgeColor="bg-blue-600 hover:bg-blue-600"
                title="MCPClient"
                footerContent={docLinkFooter}
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
