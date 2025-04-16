import { Info } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useState } from "react";

export const HowItWorksAccordion = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mb-8">
      <Collapsible
        open={isOpen}
        onOpenChange={setIsOpen}
        className="w-full space-y-2"
      >
        <div className="flex items-center justify-end">
          <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors">
            <Info className="h-4 w-4" />
            <span>How does this work?</span>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="bg-card rounded-lg p-4 shadow-lg border animate-in slide-in-from-top-2">
          <div className="text-sm text-muted-foreground space-y-4">
            <p>
              Setting up a white-labeled integration lets you securely sync data for your multi-tenant users.
            </p>

            <div>
              <h4 className="font-medium text-foreground mb-2">1. Fill out the integration form</h4>
              <ul className="list-disc pl-5 space-y-1">
                <li>Enter the integration name and select the data source</li>
                <li>Add your frontend callback URL and OAuth2 credentials</li>
              </ul>
            </div>

            <div>
              <h4 className="font-medium text-foreground mb-2">2. OAuth2 flow</h4>
              <ul className="list-disc pl-5 space-y-1">
                <li>Use the provided authorization URL generator</li>
                <li>Users are redirected back to your callback URL with a temporary code</li>
              </ul>
            </div>

            <div>
              <h4 className="font-medium text-foreground mb-2">3. Token exchange</h4>
              <ul className="list-disc pl-5 space-y-1">
                <li>Airweave exchanges the code for access and refresh tokens</li>
                <li>Tokens are securely stored with tenant metadata</li>
              </ul>
            </div>

            <div>
              <h4 className="font-medium text-foreground mb-2">4. Data synchronization</h4>
              <ul className="list-disc pl-5 space-y-1">
                <li>Airweave syncs data from source to destination</li>
                <li>Syncs are incremental, fetching only new or changed data</li>
              </ul>
            </div>

            <div>
              <h4 className="font-medium text-foreground mb-2">5. Automatic token management</h4>
              <ul className="list-disc pl-5 space-y-1">
                <li>Tokens are refreshed automatically</li>
                <li>Ensures continuous synchronization without manual intervention</li>
              </ul>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};
