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
  // Dialog open state
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;

  // Page-level commands (registered by current page)
  pageTitle: string | null;
  pageCommands: Command[];
  setPageCommands: (title: string | null, commands: Command[]) => void;
  clearPageCommands: () => void;

  // Context commands (for focused/selected items)
  contextTitle: string | null;
  contextCommands: Command[];
  setContextCommands: (title: string | null, commands: Command[]) => void;
  clearContextCommands: () => void;
}

export const useCommandStore = create<CommandStoreState>((set) => ({
  // Dialog state
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set((state) => ({ open: !state.open })),

  // Page commands
  pageTitle: null,
  pageCommands: [],
  setPageCommands: (title, commands) => set({ pageTitle: title, pageCommands: commands }),
  clearPageCommands: () => set({ pageTitle: null, pageCommands: [] }),

  // Context commands
  contextTitle: null,
  contextCommands: [],
  setContextCommands: (title, commands) => set({ contextTitle: title, contextCommands: commands }),
  clearContextCommands: () => set({ contextTitle: null, contextCommands: [] }),
}));

