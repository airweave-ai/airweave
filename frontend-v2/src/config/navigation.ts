import {
  Cable,
  FolderOpen,
  Key,
  LayoutDashboard,
  ShieldCheck,
  Webhook,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  url: string;
  icon: LucideIcon;
}

export const navItems: NavItem[] = [
  {
    title: "Dashboard",
    url: "/",
    icon: LayoutDashboard,
  },
  {
    title: "Collections",
    url: "/collections",
    icon: FolderOpen,
  },
  {
    title: "Logs",
    url: "/logs",
    icon: Cable,
  },
  {
    title: "API Keys",
    url: "/api-keys",
    icon: Key,
  },
  {
    title: "Webhooks",
    url: "/webhooks",
    icon: Webhook,
  },
  {
    title: "Auth Providers",
    url: "/auth-providers",
    icon: ShieldCheck,
  },
];
