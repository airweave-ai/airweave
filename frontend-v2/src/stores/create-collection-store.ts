import { create } from "zustand";

/** Pre-selected source info for "Start from a Source" flow */
export interface PreSelectedSource {
  shortName: string;
  name: string;
}

interface CreateCollectionState {
  /** Whether the create collection dialog is open */
  isOpen: boolean;
  /** Pre-selected source for "Start from a Source" flow */
  preSelectedSource: PreSelectedSource | null;
  /** Open the create collection dialog */
  open: () => void;
  /** Open the create collection dialog with a pre-selected source */
  openWithSource: (shortName: string, name: string) => void;
  /** Close the create collection dialog */
  close: () => void;
  /** Toggle the create collection dialog */
  toggle: () => void;
  /** Clear the pre-selected source */
  clearPreSelectedSource: () => void;
}

export const useCreateCollectionStore = create<CreateCollectionState>()(
  (set) => ({
    isOpen: false,
    preSelectedSource: null,
    open: () => set({ isOpen: true, preSelectedSource: null }),
    openWithSource: (shortName: string, name: string) =>
      set({ isOpen: true, preSelectedSource: { shortName, name } }),
    close: () => set({ isOpen: false }),
    toggle: () => set((state) => ({ isOpen: !state.isOpen })),
    clearPreSelectedSource: () => set({ preSelectedSource: null }),
  })
);
