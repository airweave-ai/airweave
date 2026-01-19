import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { MdxProvider } from "@/components/mdx";

const mdxModules = import.meta.glob<{
  default: React.ComponentType;
  frontmatter?: Record<string, unknown>;
}>("../../../fern/docs/pages/**/*.mdx");

interface MdxModule {
  Component: React.ComponentType;
  frontmatter?: Record<string, unknown>;
}

async function loadMdxModule(docPath: string): Promise<MdxModule> {
  const fullPath = `../../../fern/docs/pages/${docPath}`;
  const moduleLoader = mdxModules[fullPath];

  if (!moduleLoader) {
    throw new Error(`Documentation not found: ${docPath}`);
  }

  const module = await moduleLoader();
  return {
    Component: module.default,
    frontmatter: module.frontmatter,
  };
}

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
  const {
    data,
    isLoading: loading,
    error,
  } = useQuery({
    queryKey: ["docs-content", docPath],
    queryFn: () => loadMdxModule(docPath!),
    enabled: !!docPath,
    staleTime: Infinity, // MDX content doesn't change at runtime
    gcTime: Infinity, // Keep cached indefinitely
  });

  const content = React.useMemo(() => {
    if (!data) return null;
    const { Component } = data;
    return (
      <MdxProvider>
        <Component />
      </MdxProvider>
    );
  }, [data]);

  return {
    content,
    loading,
    error:
      error instanceof Error ? error.message : error ? String(error) : null,
    title: data?.frontmatter?.title as string | undefined,
  };
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
        <div className="animate-pulse text-sm text-slate-400">
          Loading documentation...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4 text-sm text-slate-400">
        {fallback || "Documentation not available."}
      </div>
    );
  }

  if (!content) {
    return (
      <div className="py-4 text-sm text-slate-400">
        {fallback || "No documentation available for this page."}
      </div>
    );
  }

  return <>{content}</>;
}

export default useDocsContent;
