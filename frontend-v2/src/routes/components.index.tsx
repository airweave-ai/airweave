import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Package } from "lucide-react";
import { uiComponents, type ComponentInfo } from "../components.gen";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
      className="block group"
    >
      <Card className="h-full hover:shadow-md transition-all duration-300 hover:border-primary/50">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="p-3 bg-muted rounded-lg">
              <Package className="w-6 h-6 text-primary" />
            </div>
            <Badge variant="secondary">.tsx</Badge>
          </div>
          <CardTitle className="flex items-center gap-2">
            {displayName}
            <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription className="font-mono truncate" title={component.path}>
            {component.path}
          </CardDescription>
        </CardContent>
      </Card>
    </Link>
  );
}

function ComponentsIndexPage() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">All Components</h1>
        <p className="text-muted-foreground">
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
          <div className="inline-flex items-center justify-center w-16 h-16 bg-muted rounded-full mb-4">
            <Package className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold text-foreground mb-2">
            No components found
          </h3>
          <p className="text-muted-foreground max-w-md mx-auto">
            Add components to{" "}
            <code className="px-2 py-0.5 bg-muted rounded text-primary text-sm">
              src/components/ui/
            </code>{" "}
            and they will appear here automatically.
          </p>
        </div>
      )}
    </div>
  );
}
