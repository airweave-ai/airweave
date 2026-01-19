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
      className="group block"
    >
      <Card className="hover:border-primary/50 h-full transition-all duration-300 hover:shadow-md">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="bg-muted rounded-lg p-3">
              <Package className="text-primary h-6 w-6" />
            </div>
            <Badge variant="secondary">.tsx</Badge>
          </div>
          <CardTitle className="flex items-center gap-2">
            {displayName}
            <ArrowRight className="h-4 w-4 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription
            className="truncate font-mono"
            title={component.path}
          >
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
        <h1 className="text-foreground mb-2 text-3xl font-bold">
          All Components
        </h1>
        <p className="text-muted-foreground">
          Browse and explore all available UI components. Click on a component
          to see its variants and usage examples.
        </p>
      </div>

      {/* Components Grid */}
      {uiComponents.length > 0 ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {uiComponents.map((component) => (
            <ComponentCard key={component.name} component={component} />
          ))}
        </div>
      ) : (
        <div className="py-20 text-center">
          <div className="bg-muted mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full">
            <Package className="text-muted-foreground h-8 w-8" />
          </div>
          <h3 className="text-foreground mb-2 text-xl font-semibold">
            No components found
          </h3>
          <p className="text-muted-foreground mx-auto max-w-md">
            Add components to{" "}
            <code className="bg-muted text-primary rounded px-2 py-0.5 text-sm">
              src/components/ui/
            </code>{" "}
            and they will appear here automatically.
          </p>
        </div>
      )}
    </div>
  );
}
