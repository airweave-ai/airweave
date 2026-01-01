import { createFileRoute } from "@tanstack/react-router";
import {
  Zap,
  Server,
  Route as RouteIcon,
  Shield,
  Waves,
  Sparkles,
  ExternalLink,
} from "lucide-react";

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
      icon: <Zap className="w-12 h-12 text-cyan-400" />,
      title: "Powerful Server Functions",
      description:
        "Write server-side code that seamlessly integrates with your client components. Type-safe, secure, and simple.",
    },
    {
      icon: <Server className="w-12 h-12 text-cyan-400" />,
      title: "Flexible Server Side Rendering",
      description:
        "Full-document SSR, streaming, and progressive enhancement out of the box. Control exactly what renders where.",
    },
    {
      icon: <RouteIcon className="w-12 h-12 text-cyan-400" />,
      title: "API Routes",
      description:
        "Build type-safe API endpoints alongside your application. No separate backend needed.",
    },
    {
      icon: <Shield className="w-12 h-12 text-cyan-400" />,
      title: "Strongly Typed Everything",
      description:
        "End-to-end type safety from server to client. Catch errors before they reach production.",
    },
    {
      icon: <Waves className="w-12 h-12 text-cyan-400" />,
      title: "Full Streaming Support",
      description:
        "Stream data from server to client progressively. Perfect for AI applications and real-time updates.",
    },
    {
      icon: <Sparkles className="w-12 h-12 text-cyan-400" />,
      title: "Next Generation Ready",
      description:
        "Built from the ground up for modern web applications. Deploy anywhere JavaScript runs.",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900">
      <section className="relative py-20 px-6 text-center overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-blue-500/10 to-purple-500/10"></div>
        <div className="relative max-w-5xl mx-auto">
          <div className="flex items-center justify-center gap-6 mb-6">
            <img
              src="/tanstack-circle-logo.png"
              alt="TanStack Logo"
              className="w-24 h-24 md:w-32 md:h-32"
            />
            <h1 className="text-6xl md:text-7xl font-black text-white [letter-spacing:-0.08em]">
              <span className="text-gray-300">TANSTACK</span>{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                START
              </span>
            </h1>
          </div>
          <p className="text-2xl md:text-3xl text-gray-300 mb-4 font-light">
            The framework for next generation AI applications
          </p>
          <p className="text-lg text-gray-400 max-w-3xl mx-auto mb-8">
            Full-stack framework powered by TanStack Router for React and Solid.
            Build modern applications with server functions, streaming, and type
            safety.
          </p>
          <div className="flex flex-col items-center gap-4">
            <a
              href="https://tanstack.com/start"
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-3 bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-lg transition-colors shadow-lg shadow-cyan-500/50"
            >
              Documentation
            </a>
            <p className="text-gray-400 text-sm mt-2">
              Begin your TanStack Start journey by editing{" "}
              <code className="px-2 py-1 bg-slate-700 rounded text-cyan-400">
                /src/routes/index.tsx
              </code>
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 px-6 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <div
              key={index}
              className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:border-cyan-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-cyan-500/10"
            >
              <div className="mb-4">{feature.icon}</div>
              <h3 className="text-xl font-semibold text-white mb-3">
                {feature.title}
              </h3>
              <p className="text-gray-400 leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
