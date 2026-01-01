import * as React from "react";

import { MdxProvider } from "@/components/mdx";

// Dynamically import all MDX files from fern docs
// Vite's import.meta.glob with eager: false for lazy loading
const mdxModules = import.meta.glob<{
  default: React.ComponentType;
  frontmatter?: Record<string, unknown>;
}>("../../../fern/docs/pages/**/*.mdx");

interface DocsContentResult {
  content: React.ReactNode | null;
  loading: boolean;
  error: string | null;
  title?: string;
}

/**
 * Hook to load MDX documentation content based on a path
 */
export function useDocsContent(docPath: string | null): DocsContentResult {
  const [result, setResult] = React.useState<DocsContentResult>({
    content: null,
    loading: !!docPath,
    error: null,
  });

  React.useEffect(() => {
    if (!docPath) {
      setResult({ content: null, loading: false, error: null });
      return;
    }

    const loadContent = async () => {
      setResult((prev) => ({ ...prev, loading: true, error: null }));

      try {
        // Build the full path for the import
        const fullPath = `../../../fern/docs/pages/${docPath}`;

        // Find the matching module
        const moduleLoader = mdxModules[fullPath];

        if (!moduleLoader) {
          setResult({
            content: null,
            loading: false,
            error: `Documentation not found: ${docPath}`,
          });
          return;
        }

        // Load the module
        const module = await moduleLoader();
        const MdxComponent = module.default;
        const frontmatter = module.frontmatter;

        setResult({
          content: (
            <MdxProvider>
              <MdxComponent />
            </MdxProvider>
          ),
          loading: false,
          error: null,
          title: frontmatter?.title as string | undefined,
        });
      } catch (err) {
        setResult({
          content: null,
          loading: false,
          error: err instanceof Error ? err.message : "Failed to load docs",
        });
      }
    };

    loadContent();
  }, [docPath]);

  return result;
}

/**
 * Component that renders documentation content with loading/error states
 */
export function DocsContent({
  docPath,
  fallback,
}: {
  docPath: string | null;
  fallback?: React.ReactNode;
}) {
  const { content, loading, error } = useDocsContent(docPath);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-muted-foreground animate-pulse text-sm">
          Loading documentation...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-muted-foreground py-4 text-sm">
        {fallback || "Documentation not available."}
      </div>
    );
  }

  if (!content) {
    return (
      <div className="text-muted-foreground py-4 text-sm">
        {fallback || "No documentation available for this page."}
      </div>
    );
  }

  return <>{content}</>;
}

export default useDocsContent;
