import { createFileRoute } from "@tanstack/react-router";
import {
  Database,
  Link as LinkIcon,
  RefreshCw,
  Search,
  Shield,
  Zap,
} from "lucide-react";

export const Route = createFileRoute("/")({ component: App });

function App() {
  const features = [
    {
      icon: <LinkIcon className="w-12 h-12 text-cyan-400" />,
      title: "Connect Any App",
      description:
        "Seamlessly connect to your favorite applications and services. Airweave Connect handles authentication and data flow.",
    },
    {
      icon: <Database className="w-12 h-12 text-cyan-400" />,
      title: "Unified Data Access",
      description:
        "Access all your connected data sources through a single, unified interface. No more switching between tools.",
    },
    {
      icon: <RefreshCw className="w-12 h-12 text-cyan-400" />,
      title: "Real-time Sync",
      description:
        "Keep your data synchronized in real-time. Changes are reflected instantly across all connected services.",
    },
    {
      icon: <Shield className="w-12 h-12 text-cyan-400" />,
      title: "Secure by Design",
      description:
        "Enterprise-grade security with OAuth2 authentication. Your credentials are never stored on our servers.",
    },
    {
      icon: <Search className="w-12 h-12 text-cyan-400" />,
      title: "Agentic Search",
      description:
        "Make your connected data searchable for AI agents. Transform raw data into queryable knowledge.",
    },
    {
      icon: <Zap className="w-12 h-12 text-cyan-400" />,
      title: "Lightning Fast",
      description:
        "Optimized for performance with incremental updates and smart caching. Get results in milliseconds.",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900">
      <section className="relative py-20 px-6 text-center overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-blue-500/10 to-purple-500/10"></div>
        <div className="relative max-w-5xl mx-auto">
          <div className="flex items-center justify-center gap-6 mb-6">
            <h1 className="text-6xl md:text-7xl font-black text-white [letter-spacing:-0.04em]">
              <span className="text-gray-300">AIRWEAVE</span>{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                CONNECT
              </span>
            </h1>
          </div>
          <p className="text-2xl md:text-3xl text-gray-300 mb-4 font-light">
            Make any app searchable for your agent
          </p>
          <p className="text-lg text-gray-400 max-w-3xl mx-auto mb-8">
            Connect your data sources with minimal configuration. Airweave
            transforms your raw data into queryable knowledge for AI agents.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href="https://airweave.io"
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-3 bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-lg transition-colors shadow-lg shadow-cyan-500/50"
            >
              Get Started
            </a>
            <a
              href="https://docs.airweave.io"
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-3 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-lg transition-colors"
            >
              Documentation
            </a>
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
