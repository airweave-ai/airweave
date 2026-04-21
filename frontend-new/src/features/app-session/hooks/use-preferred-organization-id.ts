import { useStore } from 'zustand';
import { appSessionStore } from '../lib/store';

export function usePreferredOrganizationId() {
  return useStore(appSessionStore, (state) => state.preferredOrganizationId);
}
