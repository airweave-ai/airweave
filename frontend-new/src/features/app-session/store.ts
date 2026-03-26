import { useStore } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { createStore } from 'zustand/vanilla';

interface AppSessionStoreState {
  clearPreferredOrganizationId: () => void;
  preferredOrganizationId: string | null;
  setPreferredOrganizationId: (organizationId: string | null) => void;
}

export const appSessionStore = createStore<AppSessionStoreState>()(
  persist(
    (set) => ({
      clearPreferredOrganizationId: () => {
        set({ preferredOrganizationId: null });
      },
      preferredOrganizationId: null,
      setPreferredOrganizationId: (organizationId) => {
        set({ preferredOrganizationId: organizationId });
      },
    }),
    {
      name: 'app-session-storage',
      partialize: (state) => ({
        preferredOrganizationId: state.preferredOrganizationId,
      }),
      storage: createJSONStorage(() => localStorage),
    },
  ),
);

export function getPreferredOrganizationId() {
  return appSessionStore.getState().preferredOrganizationId;
}

export function setPreferredOrganizationId(organizationId: string | null) {
  appSessionStore.getState().setPreferredOrganizationId(organizationId);
}

export function clearPreferredOrganizationId() {
  appSessionStore.getState().clearPreferredOrganizationId();
}

export function usePreferredOrganizationId() {
  return useStore(appSessionStore, (state) => state.preferredOrganizationId);
}
