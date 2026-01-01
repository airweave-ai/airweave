"use client"

import {
  RightSidebarTabs,
  RightSidebarPanel,
  MobileBottomNav,
  MobileRightSidebarSheet,
} from "@/components/ui/right-sidebar"

export function AppRightSidebar() {
  return (
    <>
      {/* Desktop: fixed panel and tab bar on right side */}
      <RightSidebarPanel />
      <RightSidebarTabs />
      {/* Mobile: bottom nav bar and sheet */}
      <MobileBottomNav />
      <MobileRightSidebarSheet />
    </>
  )
}

