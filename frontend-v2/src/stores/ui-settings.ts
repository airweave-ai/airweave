import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

type RightSidebarTab = "docs" | "code" | "help" | null;
export type Theme = "light" | "dark" | "system";

interface UISettingsState {
  // Left sidebar
  leftSidebarOpen: boolean;
  setLeftSidebarOpen: (open: boolean) => void;
  toggleLeftSidebar: () => void;

  // Right sidebar
  rightSidebarTab: RightSidebarTab;
  setRightSidebarTab: (tab: RightSidebarTab) => void;
  toggleRightSidebarTab: (tab: "docs" | "code" | "help") => void;

  // Theme
  theme: Theme;
  setTheme: (theme: Theme) => void;

  // Hydration tracking
  _hasHydrated: boolean;
  setHasHydrated: (hydrated: boolean) => void;
}

export const useUISettings = create<UISettingsState>()(
  persist(
    (set) => ({
      // Left sidebar - default open
      leftSidebarOpen: true,
      setLeftSidebarOpen: (open) => set({ leftSidebarOpen: open }),
      toggleLeftSidebar: () =>
        set((state) => ({ leftSidebarOpen: !state.leftSidebarOpen })),

      // Right sidebar - default closed
      rightSidebarTab: null,
      setRightSidebarTab: (tab) => set({ rightSidebarTab: tab }),
      toggleRightSidebarTab: (tab) =>
        set((state) => ({
          rightSidebarTab: state.rightSidebarTab === tab ? null : tab,
        })),

      // Theme - default to dark as it's a dev tool
      theme: "dark",
      setTheme: (theme) => set({ theme }),

      // Hydration tracking (not persisted)
      _hasHydrated: false,
      setHasHydrated: (hydrated) => set({ _hasHydrated: hydrated }),
    }),
    {
      name: "airweave-ui-settings",
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
      partialize: (state) => ({
        // Only persist these fields (exclude hydration state)
        leftSidebarOpen: state.leftSidebarOpen,
        rightSidebarTab: state.rightSidebarTab,
        theme: state.theme,
      }),
    },
  ),
);

/**
 * Hook to check if UI settings have been hydrated from localStorage.
 * Use this to prevent flash of incorrect content on initial load.
 */
export function useUISettingsHydrated() {
  const [hydrated, setHydrated] = useState(
    useUISettings.getState()._hasHydrated,
  );

  useEffect(() => {
    const unsubscribe = useUISettings.subscribe((state) =>
      setHydrated(state._hasHydrated),
    );
    // Check immediately in case it hydrated before subscription
    setHydrated(useUISettings.getState()._hasHydrated);
    return unsubscribe;
  }, []);

  return hydrated;
}
