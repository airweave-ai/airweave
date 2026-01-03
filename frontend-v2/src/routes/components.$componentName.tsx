import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Check, Code, Copy, Package } from "lucide-react";
import { useState } from "react";
import { uiComponents } from "../components.gen";
import { componentPreviews } from "../previews";

export const Route = createFileRoute("/components/$componentName")({
  component: ComponentDetailPage,
});

function toDisplayName(name: string) {
  return name
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function CodeBlock({
  code,
  language: _language = "tsx",
}: {
  code: string;
  language?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="group relative">
      <pre className="bg-muted overflow-x-auto rounded-lg border p-4">
        <code className="font-mono text-sm">{code}</code>
      </pre>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={handleCopy}
        className="absolute top-2 right-2 opacity-0 transition-opacity group-hover:opacity-100"
      >
        {copied ? (
          <Check className="text-primary h-4 w-4" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}

function VariantPreview({
  title,
  description,
  children,
  code,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  code: string;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="bg-muted/30 flex min-h-[120px] items-center justify-center p-6">
        <div className="flex flex-wrap items-center gap-4">{children}</div>
      </CardContent>
      <div className="border-t">
        <CodeBlock code={code} />
      </div>
    </Card>
  );
}

function ComponentDetailPage() {
  const { componentName } = Route.useParams();
  const component = uiComponents.find((c) => c.name === componentName);

  if (!component) {
    return (
      <div className="p-8">
        <div className="py-20 text-center">
          <div className="bg-muted mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full">
            <Package className="text-muted-foreground h-8 w-8" />
          </div>
          <h3 className="text-foreground mb-2 text-xl font-semibold">
            Component not found
          </h3>
          <p className="text-muted-foreground mb-4">
            The component "{componentName}" doesn't exist.
          </p>
          <Button variant="ghost" asChild>
            <Link to="/components">
              <ArrowLeft className="h-4 w-4" />
              Back to components
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const displayName = toDisplayName(component.name);
  const previews = componentPreviews[component.name];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Button variant="ghost" asChild className="mb-4">
          <Link to="/components">
            <ArrowLeft className="h-4 w-4" />
            Back to components
          </Link>
        </Button>
        <div className="flex items-center gap-4">
          <div className="bg-muted rounded-xl p-3">
            <Package className="text-primary h-8 w-8" />
          </div>
          <div>
            <h1 className="text-foreground text-3xl font-bold">
              {displayName}
            </h1>
            <p className="text-muted-foreground font-mono text-sm">
              {component.path}
            </p>
          </div>
        </div>
      </div>

      {/* Exports */}
      {component.exports.length > 0 && (
        <div className="mb-8">
          <h2 className="text-foreground mb-3 flex items-center gap-2 text-lg font-semibold">
            <Code className="text-primary h-5 w-5" />
            Exports
          </h2>
          <div className="flex flex-wrap gap-2">
            {component.exports.map((exp) => (
              <Badge key={exp} variant="outline" className="font-mono">
                {exp}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Import Example */}
      <div className="mb-8">
        <h2 className="text-foreground mb-3 text-lg font-semibold">Import</h2>
        <CodeBlock
          code={`import { ${component.exports.filter((e) => e !== "default").join(", ")} } from "@/components/ui/${component.name}";`}
        />
      </div>

      {/* Variants Preview */}
      {previews ? (
        <div className="space-y-6">
          <h2 className="text-foreground text-lg font-semibold">Examples</h2>
          {previews.variants.map((variant, index) => (
            <VariantPreview
              key={index}
              title={variant.title}
              description={variant.description}
              code={variant.code}
            >
              {variant.preview}
            </VariantPreview>
          ))}
        </div>
      ) : (
        <Card className="p-8 text-center">
          <CardContent className="pt-0">
            <p className="text-muted-foreground">
              No preview configuration available for this component yet.
            </p>
            <p className="text-muted-foreground mt-2 text-sm">
              Add a preview file in{" "}
              <code className="text-primary">src/previews/</code>
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
