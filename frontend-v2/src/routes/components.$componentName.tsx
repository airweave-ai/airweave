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
      <pre className="bg-slate-950 border border-slate-800 rounded-lg p-4 overflow-x-auto">
        <code className="text-sm text-slate-300 font-mono">{code}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-2 bg-slate-800 hover:bg-slate-700 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {copied ? (
          <Check className="w-4 h-4 text-emerald-400" />
        ) : (
          <Copy className="w-4 h-4 text-slate-400" />
        )}
      </button>
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
    <div className="border border-slate-700 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-slate-700 bg-slate-800/30">
        <h3 className="font-semibold text-white">{title}</h3>
        {description && (
          <p className="text-sm text-slate-400 mt-1">{description}</p>
        )}
      </div>
      <div className="p-6 bg-slate-900/50 flex items-center justify-center min-h-[120px]">
        <div className="flex flex-wrap items-center gap-4">{children}</div>
      </div>
      <div className="border-t border-slate-700">
        <CodeBlock code={code} />
      </div>
    </div>
  );
}

function ComponentDetailPage() {
  const { componentName } = Route.useParams();
  const component = uiComponents.find((c) => c.name === componentName);

  if (!component) {
    return (
      <div className="p-8">
        <div className="text-center py-20">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-800 rounded-full mb-4">
            <Package className="w-8 h-8 text-slate-600" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">
            Component not found
          </h3>
          <p className="text-slate-400 mb-4">
            The component "{componentName}" doesn't exist.
          </p>
          <Link
            to="/components"
            className="inline-flex items-center gap-2 text-emerald-400 hover:text-emerald-300"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to components
          </Link>
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
        <Link
          to="/components"
          className="inline-flex items-center gap-2 text-slate-400 hover:text-white mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to components
        </Link>
        <div className="flex items-center gap-4">
          <div className="p-3 bg-emerald-500/20 rounded-xl">
            <Package className="w-8 h-8 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">{displayName}</h1>
            <p className="text-slate-400 font-mono text-sm">{component.path}</p>
          </div>
        </div>
      </div>

      {/* Exports */}
      {component.exports.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Code className="w-5 h-5 text-emerald-400" />
            Exports
          </h2>
          <div className="flex flex-wrap gap-2">
            {component.exports.map((exp) => (
              <span
                key={exp}
                className="px-3 py-1.5 bg-slate-800 text-emerald-400 rounded-lg font-mono text-sm border border-slate-700"
              >
                {exp}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Import Example */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-white mb-3">Import</h2>
        <CodeBlock
          code={`import { ${component.exports.filter((e) => e !== "default").join(", ")} } from "@/components/ui/${component.name}";`}
        />
      </div>

      {/* Variants Preview */}
      {previews ? (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-white">Examples</h2>
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
        <div className="border border-slate-700 rounded-xl p-8 text-center">
          <p className="text-slate-400">
            No preview configuration available for this component yet.
          </p>
          <p className="text-slate-500 text-sm mt-2">
            Add a preview file in{" "}
            <code className="text-emerald-400">src/previews/</code>
          </p>
        </div>
      )}
    </div>
  );
}
