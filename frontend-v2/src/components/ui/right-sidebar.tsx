"use client";

import {
  BookOpen,
  Code2,
  HelpCircle,
  LayoutGrid,
  PanelRightIcon,
} from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { useUISettings } from "@/stores/ui-settings";

const RIGHT_SIDEBAR_WIDTH = "20rem";
const RIGHT_SIDEBAR_TAB_WIDTH = "3rem";

type TabId = "docs" | "code" | "help";

type RightSidebarContent = {
  docs?: React.ReactNode;
  code?: React.ReactNode;
  help?: React.ReactNode;
};

type RightSidebarContextProps = {
  activeTab: TabId | null;
  setActiveTab: (tab: TabId | null) => void;
  toggleTab: (tab: TabId) => void;
  content: RightSidebarContent;
  setContent: (content: RightSidebarContent) => void;
};

const RightSidebarContext =
  React.createContext<RightSidebarContextProps | null>(null);

function useRightSidebar() {
  const context = React.useContext(RightSidebarContext);
  if (!context) {
    throw new Error(
      "useRightSidebar must be used within a RightSidebarProvider.",
    );
  }
  return context;
}

/**
 * Hook for route components to register their sidebar content.
 * Content is automatically cleared when the component unmounts.
 */
function useRightSidebarContent(content: RightSidebarContent) {
  const { setContent } = useRightSidebar();

  React.useEffect(() => {
    setContent(content);
    return () => {
      setContent({});
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}

function RightSidebarProvider({
  children,
  className,
  style,
  ...props
}: React.ComponentProps<"div">) {
  // Use Zustand store for persisted active tab state
  const { rightSidebarTab, setRightSidebarTab, toggleRightSidebarTab } =
    useUISettings();

  const [content, setContent] = React.useState<RightSidebarContent>({});

  // Map Zustand state to local types
  const activeTab = rightSidebarTab as TabId | null;
  const setActiveTab = setRightSidebarTab as (tab: TabId | null) => void;
  const toggleTab = React.useCallback(
    (tab: TabId) => {
      toggleRightSidebarTab(tab);
    },
    [toggleRightSidebarTab],
  );

  const contextValue = React.useMemo<RightSidebarContextProps>(
    () => ({
      activeTab,
      setActiveTab,
      toggleTab,
      content,
      setContent,
    }),
    [activeTab, toggleTab, content],
  );

  return (
    <RightSidebarContext.Provider value={contextValue}>
      <TooltipProvider delayDuration={0}>
        <div
          data-slot="right-sidebar-wrapper"
          style={
            {
              "--right-sidebar-width": RIGHT_SIDEBAR_WIDTH,
              "--right-sidebar-tab-width": RIGHT_SIDEBAR_TAB_WIDTH,
              ...style,
            } as React.CSSProperties
          }
          className={cn("flex min-h-svh w-full", className)}
          {...props}
        >
          {children}
        </div>
      </TooltipProvider>
    </RightSidebarContext.Provider>
  );
}

const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "docs", label: "Docs", icon: <BookOpen className="size-5" /> },
  { id: "code", label: "Code", icon: <Code2 className="size-5" /> },
  { id: "help", label: "Help", icon: <HelpCircle className="size-5" /> },
];

function RightSidebarTabs({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const { activeTab, toggleTab } = useRightSidebar();

  return (
    <div
      data-slot="right-sidebar-tabs"
      className={cn(
        "fixed inset-y-0 right-0 z-10 hidden w-(--right-sidebar-tab-width) flex-col items-center bg-sidebar py-4 md:flex",
        className,
      )}
      {...props}
    >
      <div className="flex flex-col gap-2">
        {tabs.map((tab) => (
          <Tooltip key={tab.id}>
            <TooltipTrigger asChild>
              <Button
                variant={activeTab === tab.id ? "secondary" : "ghost"}
                size="icon"
                className={cn(
                  "py-2 px-4 h-auto w-10 rounded-lg transition-colors flex-col border uppercase font-mono text-xs",
                  activeTab === tab.id &&
                    "bg-sidebar-accent text-sidebar-accent-foreground",
                )}
                onClick={() => toggleTab(tab.id)}
                aria-pressed={activeTab === tab.id}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left" align="center">
              {tab.label}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}

function RightSidebarPanel({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const { activeTab, content } = useRightSidebar();

  const currentContent = activeTab ? content[activeTab] : null;

  return (
    <>
      {/* Spacer for the tab bar */}
      <div
        data-slot="right-sidebar-tab-spacer"
        className="hidden w-(--right-sidebar-tab-width) shrink-0 md:block"
      />
      {/* Spacer for the panel when open */}
      <div
        data-slot="right-sidebar-panel-spacer"
        className={cn(
          "hidden shrink-0 transition-[width] duration-200 ease-linear md:block",
          activeTab ? "w-(--right-sidebar-width)" : "w-0",
        )}
      />
      {/* The actual panel */}
      <div
        data-slot="right-sidebar-panel"
        data-state={activeTab ? "open" : "closed"}
        className={cn(
          "fixed inset-y-0 z-10 hidden h-svh w-(--right-sidebar-width) transition-[right] duration-200 ease-linear md:block",
          activeTab
            ? "right-(--right-sidebar-tab-width)"
            : "right-[calc(var(--right-sidebar-width)*-1)]",
          className,
        )}
        {...props}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-14 items-center border-b px-4">
            <h2 className="text-sm font-semibold capitalize">
              {activeTab || "Panel"}
            </h2>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {currentContent || (
              <div className="text-muted-foreground text-sm">
                No content available for this tab.
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function RightSidebarTrigger({
  className,
  ...props
}: React.ComponentProps<typeof Button>) {
  const { activeTab, setActiveTab } = useRightSidebar();

  return (
    <Button
      data-slot="right-sidebar-trigger"
      variant="ghost"
      size="icon"
      className={cn("size-7", className)}
      onClick={() => setActiveTab(activeTab ? null : "docs")}
      {...props}
    >
      <PanelRightIcon />
      <span className="sr-only">Toggle Right Sidebar</span>
    </Button>
  );
}

const mobileTabs: {
  id: TabId | "app";
  label: string;
  icon: React.ReactNode;
}[] = [
  { id: "app", label: "App", icon: <LayoutGrid className="size-5" /> },
  { id: "docs", label: "Docs", icon: <BookOpen className="size-5" /> },
  { id: "code", label: "Code", icon: <Code2 className="size-5" /> },
  { id: "help", label: "Help", icon: <HelpCircle className="size-5" /> },
];

function MobileBottomNav({ className, ...props }: React.ComponentProps<"div">) {
  const { activeTab, setActiveTab } = useRightSidebar();

  const handleTabClick = (tabId: TabId | "app") => {
    if (tabId === "app") {
      setActiveTab(null);
    } else {
      setActiveTab(tabId);
    }
  };

  // Determine which tab is active - "app" when no sidebar tab is selected
  const currentTab = activeTab || "app";

  return (
    <div
      data-slot="mobile-bottom-nav"
      className={cn(
        "fixed inset-x-0 bottom-0 z-50 flex h-16 items-center justify-around border-t bg-sidebar md:hidden",
        className,
      )}
      {...props}
    >
      {mobileTabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={cn(
            "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs transition-colors",
            currentTab === tab.id
              ? "text-sidebar-primary"
              : "text-muted-foreground hover:text-foreground",
          )}
          onClick={() => handleTabClick(tab.id)}
          aria-pressed={currentTab === tab.id}
        >
          {tab.icon}
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
}

function MobileRightSidebarSheet({
  className,
  ...props
}: React.ComponentProps<typeof Sheet> & { className?: string }) {
  const { activeTab, setActiveTab, content } = useRightSidebar();
  const isMobile = useIsMobile();

  const currentContent = activeTab ? content[activeTab] : null;
  const isOpen = activeTab !== null;

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setActiveTab(null);
    }
  };

  // Don't render the sheet on desktop - desktop uses RightSidebarPanel instead
  if (!isMobile) {
    return null;
  }

  return (
    <Sheet open={isOpen} onOpenChange={handleOpenChange} {...props}>
      <SheetContent
        side="bottom"
        className={cn("h-[70vh] rounded-t-xl", className)}
      >
        <SheetHeader className="border-b pb-4">
          <SheetTitle className="capitalize">{activeTab || "Panel"}</SheetTitle>
        </SheetHeader>
        <div className="flex-1 overflow-auto py-4">
          {currentContent || (
            <div className="text-muted-foreground text-sm">
              No content available for this tab.
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export {
  MobileBottomNav,
  MobileRightSidebarSheet,
  RightSidebarPanel,
  RightSidebarProvider,
  RightSidebarTabs,
  RightSidebarTrigger,
  useRightSidebar,
  useRightSidebarContent,
  type RightSidebarContent,
  type TabId,
};
