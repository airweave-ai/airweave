import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Check, Code, Copy, Package } from "lucide-react";
import { useState } from "react";
import { uiComponents } from "../components.gen";
import { componentPreviews } from "../previews";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
  language = "tsx",
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
    <div className="relative group">
      <pre className="bg-muted border rounded-lg p-4 overflow-x-auto">
        <code className="text-sm font-mono">{code}</code>
      </pre>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={handleCopy}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {copied ? (
          <Check className="w-4 h-4 text-primary" />
        ) : (
          <Copy className="w-4 h-4" />
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
        {description && (
          <CardDescription>{description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="p-6 bg-muted/30 flex items-center justify-center min-h-[120px]">
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
        <div className="text-center py-20">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-muted rounded-full mb-4">
            <Package className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold text-foreground mb-2">
            Component not found
          </h3>
          <p className="text-muted-foreground mb-4">
            The component "{componentName}" doesn't exist.
          </p>
          <Button variant="ghost" asChild>
            <Link to="/components">
              <ArrowLeft className="w-4 h-4" />
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
            <ArrowLeft className="w-4 h-4" />
            Back to components
          </Link>
        </Button>
        <div className="flex items-center gap-4">
          <div className="p-3 bg-muted rounded-xl">
            <Package className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">{displayName}</h1>
            <p className="text-muted-foreground font-mono text-sm">{component.path}</p>
          </div>
        </div>
      </div>

      {/* Exports */}
      {component.exports.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
            <Code className="w-5 h-5 text-primary" />
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
        <h2 className="text-lg font-semibold text-foreground mb-3">Import</h2>
        <CodeBlock
          code={`import { ${component.exports.filter((e) => e !== "default").join(", ")} } from "@/components/ui/${component.name}";`}
        />
      </div>

      {/* Variants Preview */}
      {previews ? (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-foreground">Examples</h2>
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
        <Card className="text-center p-8">
          <CardContent className="pt-0">
            <p className="text-muted-foreground">
              No preview configuration available for this component yet.
            </p>
            <p className="text-muted-foreground text-sm mt-2">
              Add a preview file in{" "}
              <code className="text-primary">src/previews/</code>
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
