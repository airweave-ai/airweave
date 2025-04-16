import React, { createContext, useContext, useState } from "react";

type SidebarState = "expanded" | "collapsed";

interface SidebarContextType {
  state: SidebarState;
  open: boolean;
  setOpen: (value: boolean | ((value: boolean) => boolean)) => void;
  isMobile: boolean;
  openMobile: boolean;
  setOpenMobile: React.Dispatch<React.SetStateAction<boolean>>;
  toggleSidebar: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SidebarState>("expanded");
  const [open, setOpen] = useState(true);
  const [openMobile, setOpenMobile] = useState(false);
  const isMobile = window.innerWidth < 768;

  const toggleSidebar = () => {
    setState(state === "expanded" ? "collapsed" : "expanded");
  };

  return (
    <SidebarContext.Provider
      value={{
        state,
        open,
        setOpen,
        isMobile,
        openMobile,
        setOpenMobile,
        toggleSidebar,
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
}

export const useSidebar = () => {
  const context = useContext(SidebarContext);
  if (context === undefined) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
};
