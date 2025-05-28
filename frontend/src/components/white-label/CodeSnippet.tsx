import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowRight, Code, Code2, Link, Terminal } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { CodeBlock } from "@/components/ui/code-block";

interface CodeSnippetProps {
  whitelabelGuid: string;
  frontendUrl?: string;
  clientId?: string;
  source?: string;
}

export const CodeSnippet = ({ whitelabelGuid, frontendUrl, clientId, source }: CodeSnippetProps) => {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<"auth" | "implementation">("auth");

  const hasWhitelabel = !!whitelabelGuid;
  const displayGuid = whitelabelGuid || "<your-white-label-id-will-be-added-here>";

  const getOAuth2Url = () => `
// Function to initiate OAuth2 flow
const initiateOAuth2Flow = async () => {
  // Get the auth URL from Airweave's backend
  const response = await fetch(\`https://api.airweave.ai/white-labels/${displayGuid}/oauth2/auth_url\`);
  const authUrl = await response.text();

  // Redirect the user to the authorization URL
  window.location.href = authUrl;
};

// Use this function in your button onClick handler:
<button onClick={initiateOAuth2Flow}>Connect to Service</button>
`.trim();

  const getCodeSnippet = () => `
// Add this script to your callback page
const airweaveOAuth = {
  init: async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
      try {
        const response = await fetch('https://api.airweave.ai/white-labels/${displayGuid}/oauth2/code', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ code })
        });

        const data = await response.json();
        console.log('Airweave connection created:', data);
      } catch (error) {
        console.error('Error creating connection with Airweave:', error);
      }
    }
  }
};

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', airweaveOAuth.init);
`.trim();

  const docLinkFooter = (
    <div className="text-xs flex items-center gap-2 text-muted-foreground">
      <span>→</span>
      <a href="https://docs.airweave.ai/api-reference/white-labels" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
        Explore the full API documentation
      </a>
    </div>
  );

  return (
    <div className={`space-y-6 ${!hasWhitelabel ? "opacity-50" : ""}`}>
      <div className="space-y-6">

        {/* Tabs */}
        <div className="flex space-x-1 p-1 rounded-md mb-4 w-fit  dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
          <Button
            variant={activeTab === "auth" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("auth")}
            className={cn(
              "rounded-sm text-xs flex items-center gap-2",
              activeTab === "auth"
                ? "shadow-sm bg-slate-100 dark:bg-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-900 dark:text-slate-200"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
            )}
          >
            <Link className="h-4 w-4" />
            <span>Get OAuth2 URL</span>
          </Button>
          <Button
            variant={activeTab === "implementation" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("implementation")}
            className={cn(
              "rounded-sm text-xs flex items-center gap-2",
              activeTab === "implementation"
                ? "shadow-sm bg-slate-100 dark:bg-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-900 dark:text-slate-200"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
            )}
          >
            <ArrowRight className="h-4 w-4" />
            <span>Callback Page Implementation</span>
          </Button>
        </div>

        {/* Auth URL Tab Content */}
        {activeTab === "auth" && (
          <div className="space-y-4">
            <CodeBlock
              code={getOAuth2Url()}
              language="javascript"
              badgeText="JS"
              badgeColor="bg-blue-600 hover:bg-blue-600"
              title="OAuth2 Authorization URL Generator"
              footerContent={docLinkFooter}
              disabled={!hasWhitelabel}
            />
            <div className="text-sm text-muted-foreground mt-2">
              <p>This function retrieves an OAuth2 authorization URL and redirects the user to authorize your application.</p>
              <p className="mt-1">Call this function when the user clicks a button to connect their account to your service.</p>
            </div>
          </div>
        )}

        {/* Implementation Code Tab Content */}
        {activeTab === "implementation" && (
          <div className="space-y-4">
            <CodeBlock
              code={getCodeSnippet()}
              language="javascript"
              badgeText="JS"
              badgeColor="bg-blue-600 hover:bg-blue-600"
              title="Callback Page Implementation"
              footerContent={docLinkFooter}
              disabled={!hasWhitelabel}
            />
            <div className="text-sm text-muted-foreground mt-2">
              <p>Add this code to your callback page that handles the OAuth2 response.</p>
              <p className="mt-1">This script automatically extracts the authorization code and completes the connection with Airweave.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
