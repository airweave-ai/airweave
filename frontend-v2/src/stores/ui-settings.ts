import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

type RightSidebarTab = "docs" | "code" | "help" | null;
export type Theme = "light" | "dark" | "system";

interface UISettingsState {
  leftSidebarOpen: boolean;
  setLeftSidebarOpen: (open: boolean) => void;
  toggleLeftSidebar: () => void;

  rightSidebarTab: RightSidebarTab;
  setRightSidebarTab: (tab: RightSidebarTab) => void;
  toggleRightSidebarTab: (tab: "docs" | "code" | "help") => void;

  theme: Theme;
  setTheme: (theme: Theme) => void;

  _hasHydrated: boolean;
  setHasHydrated: (hydrated: boolean) => void;
}

export const useUISettings = create<UISettingsState>()(
  persist(
    (set) => ({
      leftSidebarOpen: true,
      setLeftSidebarOpen: (open) => set({ leftSidebarOpen: open }),
      toggleLeftSidebar: () =>
        set((state) => ({ leftSidebarOpen: !state.leftSidebarOpen })),

      rightSidebarTab: null,
      setRightSidebarTab: (tab) => set({ rightSidebarTab: tab }),
      toggleRightSidebarTab: (tab) =>
        set((state) => ({
          rightSidebarTab: state.rightSidebarTab === tab ? null : tab,
        })),

      // Default to dark as it's a developer tool
      theme: "dark",
      setTheme: (theme) => set({ theme }),

      _hasHydrated: false,
      setHasHydrated: (hydrated) => set({ _hasHydrated: hydrated }),
    }),
    {
      name: "airweave-ui-settings",
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
      partialize: (state) => ({
        leftSidebarOpen: state.leftSidebarOpen,
        rightSidebarTab: state.rightSidebarTab,
        theme: state.theme,
      }),
    }
  )
);

/**
 * Hook to check if UI settings have been hydrated from localStorage.
 * Use this to prevent flash of incorrect content on initial load.
 *
 * Always starts as `false` to match server-rendered HTML and prevent
 * React hydration mismatches. Only updates to `true` after useEffect
 * runs (client-side only).
 */
export function useUISettingsHydrated() {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const unsubscribe = useUISettings.subscribe((state) =>
      setHydrated(state._hasHydrated)
    );
    setHydrated(useUISettings.getState()._hasHydrated);
    return unsubscribe;
  }, []);

  return hydrated;
}
