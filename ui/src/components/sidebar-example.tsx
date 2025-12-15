'use client'

import { CollectionsList } from '@/components/collections-list'
import {
  AskPanel,
  CodePanel,
  DemoPanel,
  DocsPanel,
} from '@/components/right-sidebar'
import { SidebarUser } from '@/components/sidebar-user'
import { Badge } from '@/components/ui/badge'
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
  IconApps,
  IconBook,
  IconBrandDiscord,
  IconBrandGithub,
  IconCode,
  IconHelp,
  IconKey,
  IconPhone,
  IconPlus,
  IconShield,
} from '@tabler/icons-react'
import * as React from 'react'

type RightSidebarTab = 'code' | 'docs' | 'demo' | 'ask'

export default function SidebarInsetExample() {
  const [rightSidebarOpen, setRightSidebarOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<RightSidebarTab>('code')

  const toggleRightSidebar = (tab: RightSidebarTab) => {
    if (rightSidebarOpen && activeTab === tab) {
      setRightSidebarOpen(false)
    } else {
      setActiveTab(tab)
      setRightSidebarOpen(true)
    }
  }
  const data = {
    navMain: [
      {
        title: 'Collections',
        url: '#',
        icon: <IconApps />,
        isActive: true,
        items: [
          {
            title: 'Anand‘s collection',
            url: '#',
          },
        ],
      },
      {
        title: 'Developers',
        url: '#',
        icon: <IconKey />,
        items: [
          {
            title: 'API keys',
            url: '#',
          },
          {
            title: 'Webhooks',
            url: '#',
          },
          {
            title: (
              <div className="flex gap-2">
                <div>Logs</div>
                <Badge
                  variant="outline"
                  className="text-navbar-foreground opacity-50"
                >
                  Beta
                </Badge>
              </div>
            ),
            url: '#',
          },
        ],
      },
      {
        title: 'Auth providers',
        url: '#',
        icon: <IconShield />,
      },
    ],
  }

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
              <Button className="w-full" variant="secondary">
                <IconPlus /> New collection
              </Button>
            </div>
            <SidebarMenu>
              {data.navMain.map((item) => (
                <Collapsible
                  key={item.title}
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
                    <SidebarMenuSub>
                      {item.items.map((subItem, index) => (
                        <SidebarMenuSubItem key={index}>
                          <SidebarMenuSubButton
                            render={<a href={subItem.url} />}
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
      <SidebarInset className="py-8 px-10">
        <CollectionsList />
      </SidebarInset>

      <div
        data-state={rightSidebarOpen ? 'expanded' : 'collapsed'}
        className="group/right-sidebar text-sidebar-foreground hidden md:block"
      >
        <div
          className={`
            transition-[width] duration-200 ease-linear relative bg-transparent
            ${rightSidebarOpen ? 'w-80' : 'w-0'}
          `}
        />

        <div
          className={`
            fixed inset-y-0 z-10 hidden h-svh w-82 
            transition-all duration-200 ease-linear md:flex
            p-2 pl-0
            ${rightSidebarOpen ? 'right-12 opacity-100' : '-right-82 opacity-0'}
          `}
        >
          <div className="bg-sidebar-accent rounded-xl shadow-sm flex size-full flex-col overflow-hidden text-foreground">
            <div className="flex-1 overflow-auto p-4">
              <Tabs value={activeTab} className="h-full">
                <TabsContent value="code" className="mt-0">
                  <CodePanel />
                </TabsContent>
                <TabsContent value="docs" className="mt-0">
                  <DocsPanel />
                </TabsContent>
                <TabsContent value="demo" className="mt-0 h-full">
                  <DemoPanel />
                </TabsContent>
                <TabsContent value="ask" className="mt-0">
                  <AskPanel />
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
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-sidebar-accent/20 ${
              rightSidebarOpen && activeTab === 'code'
                ? 'bg-sidebar-accent text-foreground hover:bg-sidebar-accent rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('code')}
          >
            <IconCode className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Code
          </Button>
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-sidebar-accent/20 ${
              rightSidebarOpen && activeTab === 'docs'
                ? 'bg-sidebar-accent text-foreground hover:bg-sidebar-accent rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('docs')}
          >
            <IconBook className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Docs
          </Button>
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-sidebar-accent/20 ${
              rightSidebarOpen && activeTab === 'demo'
                ? 'bg-sidebar-accent text-foreground hover:bg-sidebar-accent rounded-l-none'
                : ''
            }`}
            onClick={() => toggleRightSidebar('demo')}
          >
            <IconPhone className="size-5 flex-shrink-0" strokeWidth={1.5} />
            Demo
          </Button>
          <Button
            variant="ghost"
            className={`text-sidebar-foreground flex flex-col items-center justify-center gap-1 text-xs h-auto py-2.5 hover:text-sidebar-secondary hover:bg-sidebar-accent/20 ${
              rightSidebarOpen && activeTab === 'ask'
                ? 'bg-sidebar-accent text-foreground hover:bg-sidebar-accent rounded-l-none'
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
