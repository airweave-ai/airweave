import { Link, useLocation } from "@tanstack/react-router";
import {
  BarChart3,
  Check,
  Copy,
  CreditCard,
  Key,
  Settings,
  Star,
  Users,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { generateOrgSlug } from "@/lib/org-utils";
import type { Organization } from "@/lib/api";

interface SettingsLayoutProps {
  organization: Organization;
  children: React.ReactNode;
}

const settingsTabs = [
  { path: "settings", label: "General", icon: Settings },
  { path: "settings/members", label: "Members", icon: Users },
  { path: "settings/billing", label: "Billing", icon: CreditCard },
  { path: "settings/usage", label: "Usage", icon: BarChart3 },
] as const;

function getRoleIcon(role: string) {
  switch (role) {
    case "owner":
      return <Key className="size-3" />;
    case "admin":
      return <Settings className="size-3" />;
    default:
      return <Users className="size-3" />;
  }
}

export function SettingsLayout({
  organization,
  children,
}: SettingsLayoutProps) {
  const location = useLocation();
  const [isCopied, setIsCopied] = useState(false);

  const handleCopyId = () => {
    navigator.clipboard.writeText(organization.id);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
    toast.success("Organization ID copied to clipboard");
  };

  const orgSlug = generateOrgSlug(organization);
  const currentPath = location.pathname;

  return (
    <div className="mx-auto max-w-4xl p-6">
      {/* Header with org info */}
      <div className="mb-6 flex flex-col">
        <div className="mb-2 flex items-center gap-3">
          <h1 className="text-xl font-medium">{organization.name}</h1>

          {/* Role indicator */}
          <div className="text-primary flex items-center gap-1">
            {getRoleIcon(organization.role)}
            <span className="text-xs capitalize">{organization.role}</span>
          </div>

          {/* Primary indicator */}
          {organization.is_primary && (
            <div className="flex items-center gap-1 text-amber-500">
              <Star className="size-3" />
              <span className="text-xs">Primary</span>
            </div>
          )}
        </div>

        {/* Organization ID */}
        <button
          type="button"
          onClick={handleCopyId}
          className="text-muted-foreground hover:text-foreground group flex items-center gap-1.5 text-left text-xs transition-colors"
        >
          <span className="font-mono">{organization.id}</span>
          {isCopied ? (
            <Check className="size-3.5" />
          ) : (
            <Copy className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
          )}
        </button>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="border-border mb-8 flex border-b">
        {settingsTabs.map((tab) => {
          const isActive = currentPath === `/${orgSlug}/${tab.path}`;
          const Icon = tab.icon;

          return (
            <Link
              key={tab.path}
              to={`/$orgSlug/${tab.path}`}
              params={{ orgSlug }}
              className={cn(
                "mr-8 flex items-center gap-2 border-b-2 px-1 py-3 text-sm font-medium transition-colors",
                isActive
                  ? "border-foreground text-foreground"
                  : "text-muted-foreground hover:text-foreground border-transparent"
              )}
            >
              <Icon className="size-3.5" />
              {tab.label}
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}
