import {
  Key,
  LayoutGrid,
  Settings,
  ShieldCheck,
  Terminal,
  Webhook,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  /** Full route path with $orgSlug placeholder */
  to:
    | "/$orgSlug/collections"
    | "/$orgSlug/logs"
    | "/$orgSlug/api-keys"
    | "/$orgSlug/webhooks"
    | "/$orgSlug/auth-providers"
    | "/$orgSlug/settings";
  icon: LucideIcon;
}

export const navItems: NavItem[] = [
  {
    title: "Collections",
    to: "/$orgSlug/collections",
    icon: LayoutGrid,
  },
  {
    title: "Logs",
    to: "/$orgSlug/logs",
    icon: Terminal,
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
  {
    title: "Settings",
    to: "/$orgSlug/settings",
    icon: Settings,
  },
];
