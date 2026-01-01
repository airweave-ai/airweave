import { createFileRoute } from "@tanstack/react-router";
import {
  ExternalLink,
  Route as RouteIcon,
  Server,
  Shield,
  Sparkles,
  Waves,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";

export const Route = createFileRoute("/")({ component: App });

// Sidebar content components for the home page
function HomePageDocs() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Getting Started</h3>
      <p className="text-sm text-muted-foreground">
        Welcome to Airweave! This platform helps you make any app searchable for
        your agent by syncing data from various sources.
      </p>
      <div className="space-y-2">
        <h4 className="font-medium text-sm">Quick Links</h4>
        <ul className="space-y-1 text-sm">
          <li>
            <a
              href="https://docs.airweave.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              Documentation <ExternalLink className="size-3" />
            </a>
          </li>
          <li>
            <a
              href="https://github.com/airweave-ai/airweave"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              GitHub Repository <ExternalLink className="size-3" />
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}

function HomePageCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Example Code</h3>
      <p className="text-sm text-muted-foreground">
        Here's how to get started with the Airweave API:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`import { Airweave } from '@airweave/sdk';

const client = new Airweave({
  apiKey: process.env.AIRWEAVE_API_KEY
});

// Sync your data source
await client.sync({
  source: 'notion',
  config: { ... }
});`}</code>
      </pre>
    </div>
  );
}

function HomePageHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Need Help?</h3>
      <p className="text-sm text-muted-foreground">
        We're here to help you get the most out of Airweave.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Community Support</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Join our Discord community for help and discussions.
          </p>
        </div>
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Enterprise Support</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Contact us for dedicated enterprise support options.
          </p>
        </div>
      </div>
    </div>
  );
}

function App() {
  // Register sidebar content for this page
  useRightSidebarContent({
    docs: <HomePageDocs />,
    code: <HomePageCode />,
    help: <HomePageHelp />,
  });

  const features = [
    {
      icon: <Zap className="w-10 h-10 text-primary" />,
      title: "Powerful Server Functions",
      description:
        "Write server-side code that seamlessly integrates with your client components. Type-safe, secure, and simple.",
    },
    {
      icon: <Server className="w-10 h-10 text-primary" />,
      title: "Flexible Server Side Rendering",
      description:
        "Full-document SSR, streaming, and progressive enhancement out of the box. Control exactly what renders where.",
    },
    {
      icon: <RouteIcon className="w-10 h-10 text-primary" />,
      title: "API Routes",
      description:
        "Build type-safe API endpoints alongside your application. No separate backend needed.",
    },
    {
      icon: <Shield className="w-10 h-10 text-primary" />,
      title: "Strongly Typed Everything",
      description:
        "End-to-end type safety from server to client. Catch errors before they reach production.",
    },
    {
      icon: <Waves className="w-10 h-10 text-primary" />,
      title: "Full Streaming Support",
      description:
        "Stream data from server to client progressively. Perfect for AI applications and real-time updates.",
    },
    {
      icon: <Sparkles className="w-10 h-10 text-primary" />,
      title: "Next Generation Ready",
      description:
        "Built from the ground up for modern web applications. Deploy anywhere JavaScript runs.",
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <section className="relative py-20 px-6 text-center overflow-hidden">
        <div className="relative max-w-5xl mx-auto">
          <div className="flex items-center justify-center gap-6 mb-6">
            <img
              src="/tanstack-circle-logo.png"
              alt="TanStack Logo"
              className="w-24 h-24 md:w-32 md:h-32"
            />
            <h1 className="text-6xl md:text-7xl font-black text-foreground [letter-spacing:-0.08em]">
              <span className="text-muted-foreground">TANSTACK</span>{" "}
              <span className="text-primary">START</span>
            </h1>
          </div>
          <p className="text-2xl md:text-3xl text-foreground mb-4 font-light">
            The framework for next generation AI applications
          </p>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto mb-8">
            Full-stack framework powered by TanStack Router for React and Solid.
            Build modern applications with server functions, streaming, and type
            safety.
          </p>
          <div className="flex flex-col items-center gap-4">
            <Button asChild size="lg">
              <a
                href="https://tanstack.com/start"
                target="_blank"
                rel="noopener noreferrer"
              >
                Documentation
              </a>
            </Button>
            <p className="text-muted-foreground text-sm mt-2">
              Begin your TanStack Start journey by editing{" "}
              <code className="px-2 py-1 bg-muted rounded text-primary">
                /src/routes/index.tsx
              </code>
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 px-6 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <Card
              key={index}
              className="hover:shadow-md transition-shadow duration-300"
            >
              <CardHeader>
                <div className="mb-2">{feature.icon}</div>
                <CardTitle>{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="leading-relaxed">
                  {feature.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
