import { useEffect, useMemo } from "react";

import { type Command, useCommandStore } from "@/stores/command-store";

interface UseCommandMenuOptions {
  /** Title for the page commands group (e.g., "API Keys") */
  pageTitle?: string;
  /** Commands specific to the current page (e.g., "Create API Key" on API Keys page) */
  pageCommands?: Command[];
  /** Title for the context commands group (e.g., the selected item's name) */
  contextTitle?: string;
  /** Commands for the currently focused/selected item (e.g., "Delete" when a row is selected) */
  contextCommands?: Command[];
}

/**
 * Hook for pages to register their commands with the global command palette.
 *
 * @example
 * ```tsx
 * useCommandMenu({
 *   pageTitle: "API Keys",
 *   pageCommands: [
 *     { id: "create-key", label: "Create API Key", icon: Plus, onSelect: handleCreate }
 *   ],
 *   contextCommands: selectedKey ? [
 *     { id: "delete-key", label: "Delete API Key", icon: Trash2, onSelect: handleDelete }
 *   ] : []
 * });
 * ```
 */
export function useCommandMenu({
  pageTitle,
  pageCommands = [],
  contextTitle,
  contextCommands = [],
}: UseCommandMenuOptions = {}) {
  const setPageCommands = useCommandStore((state) => state.setPageCommands);
  const clearPageCommands = useCommandStore((state) => state.clearPageCommands);
  const setContextCommands = useCommandStore(
    (state) => state.setContextCommands
  );
  const clearContextCommands = useCommandStore(
    (state) => state.clearContextCommands
  );

  // Create stable keys for dependency tracking
  const pageCommandIds = useMemo(
    () => pageCommands.map((c) => c.id).join(","),
    [pageCommands]
  );
  const contextCommandIds = useMemo(
    () => contextCommands.map((c) => c.id).join(","),
    [contextCommands]
  );

  // Register page commands when component mounts, clear on unmount
  useEffect(() => {
    setPageCommands(pageTitle ?? null, pageCommands);
    return () => clearPageCommands();
  }, [
    pageTitle,
    pageCommandIds,
    pageCommands,
    setPageCommands,
    clearPageCommands,
  ]);

  // Register context commands reactively
  useEffect(() => {
    setContextCommands(contextTitle ?? null, contextCommands);
    return () => clearContextCommands();
  }, [
    contextTitle,
    contextCommandIds,
    contextCommands,
    setContextCommands,
    clearContextCommands,
  ]);
}

/**
 * Hook to control the command menu open state.
 */
export function useCommandMenuOpen() {
  const open = useCommandStore((state) => state.open);
  const setOpen = useCommandStore((state) => state.setOpen);
  const toggle = useCommandStore((state) => state.toggle);

  return { open, setOpen, toggle };
}
