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
    <div className="min-h-screen bg-background flex">
      {/* Left Sidebar */}
      <aside className="w-64 border-r bg-sidebar flex-shrink-0">
        <div className="sticky top-0 h-screen overflow-y-auto">
          {/* Sidebar Header */}
          <div className="p-4 border-b">
            <Link
              to="/components"
              className="flex items-center gap-3 text-sidebar-foreground hover:text-sidebar-primary transition-colors"
            >
              <div className="p-2 bg-sidebar-accent rounded-lg">
                <Layers className="w-5 h-5 text-sidebar-primary" />
              </div>
              <div>
                <h2 className="font-semibold">UI Components</h2>
                <p className="text-xs text-muted-foreground">
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
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
                    activeProps={{
                      className:
                        "bg-sidebar-accent text-sidebar-primary border border-sidebar-border",
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
          <div className="p-4 border-t mt-auto">
            <p className="text-xs text-muted-foreground text-center">
              Auto-generated from{" "}
              <code className="text-muted-foreground">components.gen.ts</code>
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
