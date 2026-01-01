import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";

import type { Theme } from "@/stores/ui-settings";

export interface ThemeOption {
  value: Theme;
  label: string;
  icon: LucideIcon;
}

export const themeOptions: ThemeOption[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];
