import { createFileRoute, Link, Outlet } from "@tanstack/react-router";
import { ChevronRight, Layers, Package } from "lucide-react";
import { uiComponents } from "../components.gen";

export const Route = createFileRoute("/components")({
  component: ComponentsLayout,
});

function toDisplayName(name: string) {
  return name
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function ComponentsLayout() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 flex">
      {/* Left Sidebar */}
      <aside className="w-64 border-r border-slate-700/50 bg-slate-900/50 backdrop-blur-sm flex-shrink-0">
        <div className="sticky top-0 h-screen overflow-y-auto">
          {/* Sidebar Header */}
          <div className="p-4 border-b border-slate-700/50">
            <Link
              to="/components"
              className="flex items-center gap-3 text-white hover:text-emerald-400 transition-colors"
            >
              <div className="p-2 bg-emerald-500/20 rounded-lg">
                <Layers className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h2 className="font-semibold">UI Components</h2>
                <p className="text-xs text-slate-500">
                  {uiComponents.length} component
                  {uiComponents.length !== 1 ? "s" : ""}
                </p>
              </div>
            </Link>
          </div>

          {/* Component List */}
          <nav className="p-2">
            <ul className="space-y-1">
              {uiComponents.map((component) => (
                <li key={component.name}>
                  <Link
                    to="/components/$componentName"
                    params={{ componentName: component.name }}
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all"
                    activeProps={{
                      className:
                        "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
                    }}
                  >
                    <Package className="w-4 h-4 flex-shrink-0" />
                    <span className="flex-1 truncate font-medium">
                      {toDisplayName(component.name)}
                    </span>
                    <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          {/* Sidebar Footer */}
          <div className="p-4 border-t border-slate-700/50 mt-auto">
            <p className="text-xs text-slate-600 text-center">
              Auto-generated from{" "}
              <code className="text-slate-500">components.gen.ts</code>
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
