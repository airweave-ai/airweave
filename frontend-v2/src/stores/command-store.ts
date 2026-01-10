import type { LucideIcon } from "lucide-react";
import { create } from "zustand";

export interface Command {
  id: string;
  label: string;
  icon?: LucideIcon;
  shortcut?: string;
  onSelect: () => void;
  keywords?: string[];
}

interface CommandStoreState {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;

  pageTitle: string | null;
  pageCommands: Command[];
  setPageCommands: (title: string | null, commands: Command[]) => void;
  clearPageCommands: () => void;

  contextTitle: string | null;
  contextCommands: Command[];
  setContextCommands: (title: string | null, commands: Command[]) => void;
  clearContextCommands: () => void;
}

export const useCommandStore = create<CommandStoreState>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set((state) => ({ open: !state.open })),

  pageTitle: null,
  pageCommands: [],
  setPageCommands: (title, commands) =>
    set({ pageTitle: title, pageCommands: commands }),
  clearPageCommands: () => set({ pageTitle: null, pageCommands: [] }),

  contextTitle: null,
  contextCommands: [],
  setContextCommands: (title, commands) =>
    set({ contextTitle: title, contextCommands: commands }),
  clearContextCommands: () => set({ contextTitle: null, contextCommands: [] }),
}));
