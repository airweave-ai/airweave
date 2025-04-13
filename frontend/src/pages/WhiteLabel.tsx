import { Plus, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { WhiteLabelTable } from "@/components/white-label/WhiteLabelTable";
import { HowItWorksAccordion } from "@/components/white-label/HowItWorksAccordion";

const WhiteLabel = () => {
  const navigate = useNavigate();

  // Mock data - in real app this would come from your API
  const whiteLabelIntegrations = [
    {
      id: "wl_123456",
      name: "Customer Portal Integration",
      frontendUrl: "https://customer.example.com/callback",
      createdAt: "2024-03-15",
    },
    {
      id: "wl_789012",
      name: "Partner Dashboard",
      frontendUrl: "https://partner.example.com/oauth",
      createdAt: "2024-03-14",
    },
    {
      id: "wl_345678",
      name: "Mobile App Integration",
      frontendUrl: "https://mobile.example.com/auth",
      createdAt: "2024-03-13",
    },
  ];

  return (
    <div className="container mx-auto pb-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">White Labels</h1>
          <p className="text-muted-foreground mt-2">
            Manage your OAuth2 white labels for different applications.
          </p>
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={() => window.open("https://docs.airweave.ai/white-labeling", "_blank")}
          >
            <Lightbulb className="h-4 w-4" />
            Learn More
          </Button>
          <Button onClick={() => navigate("/white-label/create")}>
            <Plus className="mr-2 h-4 w-4" />
            New White Label
          </Button>
        </div>
      </div>

      <HowItWorksAccordion />

      <WhiteLabelTable />
    </div>
  );
};

export default WhiteLabel;
