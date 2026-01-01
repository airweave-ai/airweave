import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Package } from "lucide-react";
import { uiComponents, type ComponentInfo } from "../components.gen";

export const Route = createFileRoute("/components/")({
  component: ComponentsIndexPage,
});

function toDisplayName(name: string) {
  return name
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function ComponentCard({ component }: { component: ComponentInfo }) {
  const displayName = toDisplayName(component.name);

  return (
    <Link
      to="/components/$componentName"
      params={{ componentName: component.name }}
      className="group relative bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:border-emerald-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-emerald-500/10 block"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="p-3 bg-emerald-500/10 rounded-lg">
          <Package className="w-6 h-6 text-emerald-400" />
        </div>
        <span className="text-xs font-mono text-slate-500 bg-slate-900/50 px-2 py-1 rounded">
          .tsx
        </span>
      </div>

      <h3 className="text-xl font-semibold text-white mb-2 flex items-center gap-2">
        {displayName}
        <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
      </h3>

      <p
        className="text-sm text-slate-400 font-mono truncate"
        title={component.path}
      >
        {component.path}
      </p>

      <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
    </Link>
  );
}

function ComponentsIndexPage() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">All Components</h1>
        <p className="text-slate-400">
          Browse and explore all available UI components. Click on a component
          to see its variants and usage examples.
        </p>
      </div>

      {/* Components Grid */}
      {uiComponents.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
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
    </div>
  );
}
