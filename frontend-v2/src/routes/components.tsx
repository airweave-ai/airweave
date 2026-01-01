import { createFileRoute, Link } from "@tanstack/react-router";
import { Package, Code, ExternalLink, Layers } from "lucide-react";
import { uiComponents, type ComponentInfo } from "../components.gen";

export const Route = createFileRoute("/components")({ component: ComponentsPage });

function ComponentCard({ component }: { component: ComponentInfo }) {
  // Convert kebab-case or snake_case to Title Case
  const displayName = component.name
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return (
    <div className="group relative bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:border-emerald-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-emerald-500/10">
      <div className="flex items-start justify-between mb-4">
        <div className="p-3 bg-emerald-500/10 rounded-lg">
          <Package className="w-6 h-6 text-emerald-400" />
        </div>
        <span className="text-xs font-mono text-slate-500 bg-slate-900/50 px-2 py-1 rounded">
          .tsx
        </span>
      </div>

      <h3 className="text-xl font-semibold text-white mb-2">{displayName}</h3>

      <p className="text-sm text-slate-400 font-mono mb-4 truncate" title={component.path}>
        {component.path}
      </p>

      {component.exports.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Code className="w-3 h-3" />
            <span>Exports</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {component.exports.map((exp) => (
              <span
                key={exp}
                className="text-xs font-mono px-2 py-1 bg-slate-900/70 text-emerald-400 rounded border border-slate-700"
              >
                {exp}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
    </div>
  );
}

function ComponentsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900">
      {/* Header Section */}
      <section className="relative py-16 px-6 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-cyan-500/10" />
        <div className="relative max-w-6xl mx-auto">
          <div className="flex items-center gap-4 mb-4">
            <div className="p-3 bg-emerald-500/20 rounded-xl">
              <Layers className="w-8 h-8 text-emerald-400" />
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-white">
              UI Components
            </h1>
          </div>
          <p className="text-lg text-slate-400 max-w-2xl">
            Browse all available UI components in the{" "}
            <code className="px-2 py-0.5 bg-slate-800 rounded text-emerald-400 text-sm">
              src/components/ui
            </code>{" "}
            folder. This list is auto-generated from your component files.
          </p>
          <div className="mt-6 flex items-center gap-2 text-sm text-slate-500">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/50 rounded-full border border-slate-700">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              {uiComponents.length} component{uiComponents.length !== 1 ? "s" : ""} found
            </span>
          </div>
        </div>
      </section>

      {/* Components Grid */}
      <section className="py-12 px-6 max-w-6xl mx-auto">
        {uiComponents.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {uiComponents.map((component) => (
              <ComponentCard key={component.name} component={component} />
            ))}
          </div>
        ) : (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-800 rounded-full mb-4">
              <Package className="w-8 h-8 text-slate-600" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">
              No components found
            </h3>
            <p className="text-slate-400 max-w-md mx-auto">
              Add components to{" "}
              <code className="px-2 py-0.5 bg-slate-800 rounded text-emerald-400 text-sm">
                src/components/ui/
              </code>{" "}
              and they will appear here automatically.
            </p>
          </div>
        )}
      </section>

      {/* Footer info */}
      <section className="py-8 px-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-center gap-2 text-xs text-slate-600">
          <span>Auto-generated from</span>
          <code className="px-2 py-1 bg-slate-800/50 rounded text-slate-500">
            components.gen.ts
          </code>
        </div>
      </section>
    </div>
  );
}

