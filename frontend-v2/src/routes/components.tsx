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
    <div className="bg-background flex min-h-screen">
      {/* Left Sidebar */}
      <aside className="bg-sidebar w-64 flex-shrink-0 border-r">
        <div className="sticky top-0 h-screen overflow-y-auto">
          {/* Sidebar Header */}
          <div className="border-b p-4">
            <Link
              to="/components"
              className="text-sidebar-foreground hover:text-sidebar-primary flex items-center gap-3 transition-colors"
            >
              <div className="bg-sidebar-accent rounded-lg p-2">
                <Layers className="text-sidebar-primary h-5 w-5" />
              </div>
              <div>
                <h2 className="font-semibold">UI Components</h2>
                <p className="text-muted-foreground text-xs">
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
                    className="group text-muted-foreground hover:text-foreground hover:bg-accent flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all"
                    activeProps={{
                      className:
                        "bg-sidebar-accent text-sidebar-primary border border-sidebar-border",
                    }}
                  >
                    <Package className="h-4 w-4 flex-shrink-0" />
                    <span className="flex-1 truncate font-medium">
                      {toDisplayName(component.name)}
                    </span>
                    <ChevronRight className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          {/* Sidebar Footer */}
          <div className="mt-auto border-t p-4">
            <p className="text-muted-foreground text-center text-xs">
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
