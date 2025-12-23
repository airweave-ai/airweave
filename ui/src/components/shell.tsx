'use client'

import {
  AskPanel,
  CodePanel,
  DemoPanel,
  DocsPanel,
} from '@/components/right-sidebar'
import { SidebarUser } from '@/components/sidebar-user'
import { Button } from '@/components/ui/button'
import { Collapsible } from '@/components/ui/collapsible'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import {
  IconAnalyze,
  IconApps,
  IconBook,
  IconBrandDiscord,
  IconBrandGithub,
  IconCode,
  IconHelp,
  IconKey,
  IconPhone,
  IconPlug,
  IconSearch,
  IconShield,
  IconWebhook,
} from '@tabler/icons-react'
import { useLocation } from '@tanstack/react-router'
import * as React from 'react'

type RightSidebarTab = 'code' | 'docs' | 'demo' | 'ask'

interface NavItem {
  title: string
  url: string
  icon: React.ReactNode
  isActive?: boolean
  items?: Array<{ title: string; url: string }>
}

interface ShellProps {
  children: React.ReactNode
  navItems?: NavItem[]
  onNewCollectionClick?: () => void
  code?: React.ReactNode
  docs?: React.ReactNode
  askTitle?: string
  askDescription?: string
  askSuggestions?: string[]
}

export function Shell({
  children,
  navItems,
  onNewCollectionClick,
  code,
  docs,
  askTitle,
  askDescription,
  askSuggestions,
}: ShellProps) {
  const [rightSidebarOpen, setRightSidebarOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<RightSidebarTab>('code')
  const location = useLocation()

  const toggleRightSidebar = (tab: RightSidebarTab) => {
    if (rightSidebarOpen && activeTab === tab) {
      setRightSidebarOpen(false)
    } else {
      setActiveTab(tab)
      setRightSidebarOpen(true)
    }
  }

  // Helper to check if a nav item is active based on current URL
  const isNavItemActive = (url: string) => {
    if (url === '#') return false
    if (url === '/') return location.pathname === '/'
    return location.pathname === url
  }

  const defaultNavItems: NavItem[] = [
    {
      title: 'Dashboard',
      url: '/dashboard',
      icon: <IconAnalyze />,
    },
    {
      title: 'Collections',
      url: '/collections',
      icon: <IconApps />,
      items: [
        {
          title: "Anand's collection",
          url: '/collections/anands-collection',
        },
      ],
    },
    {
      title: 'Source Connections',
      url: '/source-connections',
      icon: <IconPlug />,
    },
    {
      title: 'API keys',
      url: '#',
      icon: <IconKey />,
    },
    {
      title: 'Webhooks',
      url: '#',
      icon: <IconWebhook />,
    },
    {
      title: 'Auth providers',
      url: '#',
      icon: <IconShield />,
    },
  ]

  // Apply isActive based on current URL
  const navMain = (navItems || defaultNavItems).map((item) => ({
    ...item,
    isActive: isNavItemActive(item.url),
  }))

  return (
    <SidebarProvider>
      <Sidebar variant="inset">
        <SidebarContent>
          <SidebarGroup>
            <div className="p-2">
              <img
                src="https://app.airweave.ai/logo-airweave-lightbg.svg"
                alt="Airweave"
                className="invert w-28"
              />
            </div>
            <div className="py-4">
              <Button
                className="w-full dark:bg-foreground dark:text-background"
                variant="secondary"
                onClick={onNewCollectionClick}
              >
                <IconSearch />
                Search your data
              </Button>
            </div>
            <SidebarMenu>
              {navMain.map((item, index) => (
                <Collapsible
                  key={index}
                  defaultOpen={item.isActive}
                  render={<SidebarMenuItem />}
                >
                  <SidebarMenuButton
                    render={<a href={item.url} />}
                    isActive={item.isActive}
                  >
                    {item.icon}
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                  {item.items && item.items.length > 0 && (
                    <SidebarMenuSub className="mr-0 pr-0">
                      {item.items.map((subItem, index) => (
                        <SidebarMenuSubItem key={index}>
                          <SidebarMenuSubButton
                            render={<a href={subItem.url} />}
                            isActive={isNavItemActive(subItem.url)}
                          >
                            {subItem.title}
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      ))}
                    </SidebarMenuSub>
                  )}
                </Collapsible>
              ))}
            </SidebarMenu>
          </SidebarGroup>
          <SidebarGroup className="mt-auto">
            <SidebarUser
              user={{
                name: 'Anand Chowdhary',
                avatar: 'https://github.com/AnandChowdhary.png',
              }}
            />
          </SidebarGroup>
          <SidebarTrigger className="absolute top-5 right-2.5" />
        </SidebarContent>
        <SidebarRail />
      </Sidebar>
      <SidebarInset className="h-[calc(100vh-1rem)] overflow-auto ">
        {children}
      </SidebarInset>

      <div
        data-state={rightSidebarOpen ? 'expanded' : 'collapsed'}
        className="group/right-sidebar text-sidebar-foreground hidden md:block"
      >
        <div
          className={`
            transition-[width] duration-200 ease-linear relative bg-transparent
            ${rightSidebarOpen ? 'w-96' : 'w-0'}
          `}
        />

        <div
          className={`
            fixed inset-y-0 z-10 hidden h-svh w-98 
            transition-all duration-200 ease-linear md:flex
            p-2 pl-0
            ${rightSidebarOpen ? 'right-12 opacity-100' : '-right-96 opacity-0'}
          `}
        >
          <div className="bg-background rounded-xl shadow-sm flex size-full flex-col overflow-hidden text-foreground">
            <div className="flex-1 overflow-auto">
              <Tabs value={activeTab} className="h-full">
                <TabsContent value="code" className="mt-0">
                  {code || <CodePanel />}
                </TabsContent>
                <TabsContent value="docs" className="mt-0 p-0">
                  {docs || <DocsPanel />}
                </TabsContent>
                <TabsContent value="demo" className="mt-0 h-full">
                  <DemoPanel />
                </TabsContent>
                <TabsContent value="ask" className="mt-0">
                  <AskPanel
                    title={askTitle}
                    description={askDescription}
                    suggestions={askSuggestions}
                  />
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      </div>
      <div className="pr-1.5 py-4 flex flex-col gap-2 justify-between z-20 relative">
        <div className="flex flex-col">
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-background/20 ${
              rightSidebarOpen && activeTab === 'code'
                ? 'bg-background text-foreground hover:bg-background rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('code')}
          >
            <IconCode className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Code
          </Button>
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-background/20 ${
              rightSidebarOpen && activeTab === 'docs'
                ? 'bg-background text-foreground hover:bg-background rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('docs')}
          >
            <IconBook className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Docs
          </Button>
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-background/20 ${
              rightSidebarOpen && activeTab === 'demo'
                ? 'bg-background text-foreground hover:bg-background rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('demo')}
          >
            <IconPhone className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Demo
          </Button>
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-background/20 ${
              rightSidebarOpen && activeTab === 'ask'
                ? 'bg-background text-foreground hover:bg-background rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('ask')}
          >
            <IconHelp className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Ask
          </Button>
        </div>
        <div className="flex flex-col gap-2 justify-center items-center">
          <Button
            size="icon-lg"
            variant="ghost"
            className="text-sidebar-foreground"
          >
            <IconBrandGithub className="size-5" strokeWidth={1.5} />
            <span className="sr-only">GitHub</span>
          </Button>
          <Button
            size="icon-lg"
            variant="ghost"
            className="text-sidebar-foreground"
          >
            <IconBrandDiscord className="size-5" strokeWidth={1.5} />
            <span className="sr-only">Discord</span>
          </Button>
        </div>
      </div>
    </SidebarProvider>
  )
}
