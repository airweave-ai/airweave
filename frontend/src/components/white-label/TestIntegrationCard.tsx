import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ExternalLink } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

interface TestIntegrationCardProps {
  whitelabelId: string | undefined;
  isCard?: boolean;
  title?: string;
  description?: string;
}

export function TestIntegrationCard({
  whitelabelId,
  isCard = true,
  title = "Test Your Integration",
  description = "Try out the OAuth2 flow with your new integration."
}: TestIntegrationCardProps) {
  const [isLoading, setIsLoading] = useState(false);

  // Kick off the OAuth2 flow
  const initiateOAuth2Flow = async () => {
    if (!whitelabelId) return;
    try {
      setIsLoading(true);
      const response = await apiClient.get(
        `/connections/oauth2/white-label/${whitelabelId}/auth_url`
      );
      if (!response.ok) {
        throw new Error(`Failed to get auth URL. Status: ${response.status}`);
      }
      const authUrl = await response.text();

      // Remove any quotes from the URL and ensure it's a valid URL
      const cleanUrl = authUrl.trim().replace(/^["'](.+)["']$/, '$1');
      if (!cleanUrl.startsWith('http')) {
        throw new Error('Invalid auth URL received');
      }

      // Replace current URL with the OAuth2 URL
      window.location.replace(cleanUrl);

    } catch (error) {
      console.error("Error initiating OAuth2 flow:", error);
      toast.error("Failed to initiate OAuth2 flow");
      setIsLoading(false);
    }
  };

  const content = (
    <>
      {isLoading ? (
        <div className="flex items-center justify-center p-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground mb-4">
            Click the button below to test your OAuth2 flow. You'll be redirected to complete authentication.
          </p>
          <Button
            onClick={initiateOAuth2Flow}
            disabled={!whitelabelId}
            className="flex items-center gap-2"
          >
            <span>Try OAuth2 Flow</span>
            <ExternalLink className="h-4 w-4" />
          </Button>
        </>
      )}
    </>
  );

  if (!isCard) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
        {content}
      </div>
    );
  }

  return (
    <Card className={!whitelabelId ? "opacity-50 pointer-events-none" : ""}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {content}
      </CardContent>
    </Card>
  );
}
