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
  /** Full route path with $orgSlug placeholder */
  to:
    | "/$orgSlug"
    | "/$orgSlug/collections"
    | "/$orgSlug/logs"
    | "/$orgSlug/api-keys"
    | "/$orgSlug/webhooks"
    | "/$orgSlug/auth-providers";
  icon: LucideIcon;
}

export const navItems: NavItem[] = [
  {
    title: "Dashboard",
    to: "/$orgSlug",
    icon: LayoutDashboard,
  },
  {
    title: "Collections",
    to: "/$orgSlug/collections",
    icon: FolderOpen,
  },
  {
    title: "Logs",
    to: "/$orgSlug/logs",
    icon: Cable,
  },
  {
    title: "API Keys",
    to: "/$orgSlug/api-keys",
    icon: Key,
  },
  {
    title: "Webhooks",
    to: "/$orgSlug/webhooks",
    icon: Webhook,
  },
  {
    title: "Auth Providers",
    to: "/$orgSlug/auth-providers",
    icon: ShieldCheck,
  },
];
