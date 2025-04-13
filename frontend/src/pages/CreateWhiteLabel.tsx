import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { WhiteLabelForm } from "@/components/white-label/WhiteLabelForm";
import { CodeSnippet } from "@/components/white-label/CodeSnippet";
import { HowItWorksAccordion } from "@/components/white-label/HowItWorksAccordion";
import { TestIntegrationCard } from "@/components/white-label/TestIntegrationCard";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface WhiteLabelData {
  id: string;
  name: string;
  source_short_name: string;
  redirect_url: string;
  client_id: string;
}

const CreateWhiteLabel = () => {
  const navigate = useNavigate();
  const [whiteLabel, setWhiteLabel] = useState<WhiteLabelData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSuccess = (data: WhiteLabelData) => {
    setIsLoading(false);
    setWhiteLabel(data);
  };

  return (
    <div className="container mx-auto pb-8 space-y-8">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/white-label")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Create White Label Integration</h1>
          <p className="text-muted-foreground mt-2">
            Configure a new OAuth2 integration for your application.
          </p>
        </div>
      </div>

      <HowItWorksAccordion />

      <div className="space-y-8">
        {/* Form Card */}
        <Card>
          <CardHeader>
            <CardTitle>Integration Configuration</CardTitle>
            <CardDescription>
              Set up your white label integration details. These parameters will be used to generate your integration code.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <WhiteLabelForm onSuccess={handleSuccess} />
          </CardContent>
        </Card>

        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : (
          <>
            {/* Code Snippet Card */}
            <Card className={!whiteLabel?.id ? "opacity-50 pointer-events-none" : ""}>
              <CardHeader>
                <CardTitle>Integration Code</CardTitle>
                <CardDescription>
                  Copy these code snippets to implement the OAuth2 flow in your application.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <CodeSnippet
                  whitelabelGuid={whiteLabel?.id}
                  frontendUrl={whiteLabel?.redirect_url}
                  clientId={whiteLabel?.client_id}
                  source={whiteLabel?.source_short_name}
                />
              </CardContent>
            </Card>

            {/* Test Integration Card */}
            <TestIntegrationCard whitelabelId={whiteLabel?.id} />
          </>
        )}

        {whiteLabel && (
          <div className="flex gap-4 pt-4">
            <Button onClick={() => navigate(`/white-label/${whiteLabel.id}`)}>
              Go to integration dashboard
            </Button>
            <Button onClick={() => navigate("/white-label")} variant="outline">
              Back to list
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreateWhiteLabel;
