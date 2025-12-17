'use client'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SidebarMenuButton } from '@/components/ui/sidebar'
import {
  IconChartBar,
  IconCheck,
  IconCircleDashed,
  IconCircleDashedCheck,
  IconCreditCard,
  IconDeviceLaptop,
  IconLogout,
  IconMoon,
  IconPlus,
  IconSettings,
  IconSun,
  IconSunMoon,
  IconSwitch3,
  IconUsers,
} from '@tabler/icons-react'
import { useTheme } from 'next-themes'

export function SidebarUser({
  user,
}: {
  user: { name: string; avatar: string }
}) {
  const { theme, setTheme } = useTheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <SidebarMenuButton className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground" />
        }
      >
        <Avatar className="size-6 rounded-lg">
          <AvatarImage src={user.avatar} alt={user.name} />
          <AvatarFallback className="rounded-lg">CN</AvatarFallback>
        </Avatar>
        <div className="grid flex-1 text-left text-sm leading-tight">
          <span className="truncate font-medium">{user.name}</span>
        </div>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuItem>
            <IconSettings />
            Settings
            <DropdownMenuShortcut>⇧⌘S</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem>
            <IconUsers />
            Members
          </DropdownMenuItem>
          <DropdownMenuItem>
            <IconChartBar />
            Usage
          </DropdownMenuItem>
          <DropdownMenuItem>
            <IconCreditCard />
            Billing
          </DropdownMenuItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <IconSunMoon />
              Theme
            </DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent>
                <DropdownMenuGroup>
                  <DropdownMenuItem onClick={() => setTheme('system')}>
                    <IconDeviceLaptop />
                    System
                    {theme === 'system' && <IconCheck />}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setTheme('light')}>
                    <IconSun />
                    Light
                    {theme === 'light' && <IconCheck />}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setTheme('dark')}>
                    <IconMoon />
                    Dark
                    {theme === 'dark' && <IconCheck />}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuSubContent>
            </DropdownMenuPortal>
          </DropdownMenuSub>
          <DropdownMenuSeparator />
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <IconSwitch3 />
              Switch organization
            </DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent>
                <DropdownMenuGroup>
                  <DropdownMenuItem>
                    <IconCircleDashedCheck />
                    Anand Chowdhary
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <IconCircleDashed />
                    FirstQuadrant
                  </DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem>
                    <IconPlus />
                    Create organization
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuSubContent>
            </DropdownMenuPortal>
          </DropdownMenuSub>
        </DropdownMenuGroup>
        <DropdownMenuGroup>
          <DropdownMenuItem variant="destructive">
            <IconLogout />
            Logout
            <DropdownMenuShortcut>⇧⌘Q</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
