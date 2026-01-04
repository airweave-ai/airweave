import { create } from "zustand";

interface CreateCollectionState {
  /** Whether the create collection dialog is open */
  isOpen: boolean;
  /** Open the create collection dialog */
  open: () => void;
  /** Close the create collection dialog */
  close: () => void;
  /** Toggle the create collection dialog */
  toggle: () => void;
}

export const useCreateCollectionStore = create<CreateCollectionState>()(
  (set) => ({
    isOpen: false,
    open: () => set({ isOpen: true }),
    close: () => set({ isOpen: false }),
    toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  })
);
