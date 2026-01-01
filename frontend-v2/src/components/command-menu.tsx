"use client";

import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { navItems } from "@/config/navigation";
import { themeOptions } from "@/config/theme";
import { useCommandMenuOpen } from "@/hooks/use-command-menu";
import { useCommandStore } from "@/stores/command-store";
import { useUISettings } from "@/stores/ui-settings";

export function CommandMenu() {
  const { open, setOpen } = useCommandMenuOpen();
  const navigate = useNavigate();
  const setTheme = useUISettings((state) => state.setTheme);

  // Get commands from store
  const pageTitle = useCommandStore((state) => state.pageTitle);
  const pageCommands = useCommandStore((state) => state.pageCommands);
  const contextTitle = useCommandStore((state) => state.contextTitle);
  const contextCommands = useCommandStore((state) => state.contextCommands);

  // Register keyboard shortcut
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(!open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, setOpen]);

  const runCommand = (callback: () => void) => {
    setOpen(false);
    callback();
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen} showCloseButton={false}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        {/* Context Commands - Show first when available */}
        {contextCommands.length > 0 && (
          <>
            <CommandGroup heading={contextTitle ?? "Actions"}>
              {contextCommands.map((command) => (
                <CommandItem
                  key={command.id}
                  value={command.label}
                  keywords={command.keywords}
                  onSelect={() => runCommand(command.onSelect)}
                >
                  {command.icon && <command.icon className="size-4" />}
                  <span>{command.label}</span>
                  {command.shortcut && (
                    <CommandShortcut>{command.shortcut}</CommandShortcut>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {/* Page Commands */}
        {pageCommands.length > 0 && (
          <>
            <CommandGroup heading={pageTitle ?? "Actions"}>
              {pageCommands.map((command) => (
                <CommandItem
                  key={command.id}
                  value={command.label}
                  keywords={command.keywords}
                  onSelect={() => runCommand(command.onSelect)}
                >
                  {command.icon && <command.icon className="size-4" />}
                  <span>{command.label}</span>
                  {command.shortcut && (
                    <CommandShortcut>{command.shortcut}</CommandShortcut>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {/* Navigation */}
        <CommandGroup heading="Navigation">
          {navItems.map((item) => (
            <CommandItem
              key={item.url}
              value={item.title}
              onSelect={() => runCommand(() => navigate({ to: item.url }))}
            >
              <item.icon className="size-4" />
              <span>Go to {item.title}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        {/* Theme */}
        <CommandGroup heading="Theme">
          {themeOptions.map((option) => (
            <CommandItem
              key={option.value}
              value={option.label}
              onSelect={() => runCommand(() => setTheme(option.value))}
            >
              <option.icon className="size-4" />
              <span>{option.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
