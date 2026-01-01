"use client"

import * as React from "react"
import { BookOpen, Code2, HelpCircle, PanelRightIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const RIGHT_SIDEBAR_WIDTH = "20rem"
const RIGHT_SIDEBAR_TAB_WIDTH = "3rem"

type TabId = "docs" | "code" | "help"

type RightSidebarContent = {
  docs?: React.ReactNode
  code?: React.ReactNode
  help?: React.ReactNode
}

type RightSidebarContextProps = {
  activeTab: TabId | null
  setActiveTab: (tab: TabId | null) => void
  toggleTab: (tab: TabId) => void
  content: RightSidebarContent
  setContent: (content: RightSidebarContent) => void
}

const RightSidebarContext = React.createContext<RightSidebarContextProps | null>(null)

function useRightSidebar() {
  const context = React.useContext(RightSidebarContext)
  if (!context) {
    throw new Error("useRightSidebar must be used within a RightSidebarProvider.")
  }
  return context
}

/**
 * Hook for route components to register their sidebar content.
 * Content is automatically cleared when the component unmounts.
 */
function useRightSidebarContent(content: RightSidebarContent) {
  const { setContent } = useRightSidebar()

  React.useEffect(() => {
    setContent(content)
    return () => {
      setContent({})
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}

function RightSidebarProvider({
  children,
  className,
  style,
  ...props
}: React.ComponentProps<"div">) {
  const [activeTab, setActiveTab] = React.useState<TabId | null>(null)
  const [content, setContent] = React.useState<RightSidebarContent>({})

  const toggleTab = React.useCallback((tab: TabId) => {
    setActiveTab((current) => (current === tab ? null : tab))
  }, [])

  const contextValue = React.useMemo<RightSidebarContextProps>(
    () => ({
      activeTab,
      setActiveTab,
      toggleTab,
      content,
      setContent,
    }),
    [activeTab, toggleTab, content]
  )

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
  )
}

const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "docs", label: "Documentation", icon: <BookOpen className="size-5" /> },
  { id: "code", label: "Code", icon: <Code2 className="size-5" /> },
  { id: "help", label: "Help", icon: <HelpCircle className="size-5" /> },
]

function RightSidebarTabs({ className, ...props }: React.ComponentProps<"div">) {
  const { activeTab, toggleTab } = useRightSidebar()

  return (
    <div
      data-slot="right-sidebar-tabs"
      className={cn(
        "fixed inset-y-0 right-0 z-10 hidden w-(--right-sidebar-tab-width) flex-col items-center border-l bg-sidebar py-4 md:flex",
        className
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
                  "size-10 rounded-lg transition-colors",
                  activeTab === tab.id && "bg-sidebar-accent text-sidebar-accent-foreground"
                )}
                onClick={() => toggleTab(tab.id)}
                aria-pressed={activeTab === tab.id}
              >
                {tab.icon}
                <span className="sr-only">{tab.label}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left" align="center">
              {tab.label}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </div>
  )
}

function RightSidebarPanel({ className, ...props }: React.ComponentProps<"div">) {
  const { activeTab, content } = useRightSidebar()

  const currentContent = activeTab ? content[activeTab] : null

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
          activeTab ? "w-(--right-sidebar-width)" : "w-0"
        )}
      />
      {/* The actual panel */}
      <div
        data-slot="right-sidebar-panel"
        data-state={activeTab ? "open" : "closed"}
        className={cn(
          "fixed inset-y-0 z-10 hidden h-svh w-(--right-sidebar-width) border-l bg-sidebar transition-[right] duration-200 ease-linear md:block",
          activeTab
            ? "right-(--right-sidebar-tab-width)"
            : "right-[calc(var(--right-sidebar-width)*-1)]",
          className
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
  )
}

function RightSidebarTrigger({
  className,
  ...props
}: React.ComponentProps<typeof Button>) {
  const { activeTab, setActiveTab } = useRightSidebar()

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
  )
}

export {
  RightSidebarProvider,
  RightSidebarTabs,
  RightSidebarPanel,
  RightSidebarTrigger,
  useRightSidebar,
  useRightSidebarContent,
  type TabId,
  type RightSidebarContent,
}

