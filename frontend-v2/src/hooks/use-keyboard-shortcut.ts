import { useEffect } from "react";

type KeyboardModifiers = {
  /** Require Cmd (Mac) or Ctrl (Windows/Linux) */
  meta?: boolean;
  /** Require Ctrl key */
  ctrl?: boolean;
  /** Require Shift key */
  shift?: boolean;
  /** Require Alt/Option key */
  alt?: boolean;
};

type KeyboardShortcutOptions = KeyboardModifiers & {
  /** The key to listen for (e.g., "Escape", "k", "Enter") */
  key: string;
  /** Callback when shortcut is triggered */
  onKeyDown: (event: KeyboardEvent) => void;
  /** Whether the shortcut is enabled (default: true) */
  enabled?: boolean;
  /** Prevent default browser behavior (default: true) */
  preventDefault?: boolean;
};

/**
 * Hook for handling keyboard shortcuts.
 *
 * @example
 * ```tsx
 * // Simple ESC key handler
 * useKeyboardShortcut({
 *   key: "Escape",
 *   onKeyDown: () => setModalOpen(false),
 * });
 *
 * // Cmd+K / Ctrl+K shortcut
 * useKeyboardShortcut({
 *   key: "k",
 *   meta: true,
 *   onKeyDown: () => setOpen(!open),
 * });
 *
 * // Conditional shortcut
 * useKeyboardShortcut({
 *   key: "Escape",
 *   onKeyDown: handleClose,
 *   enabled: isModalOpen,
 * });
 * ```
 */
export function useKeyboardShortcut({
  key,
  onKeyDown,
  enabled = true,
  preventDefault = true,
  meta = false,
  ctrl = false,
  shift = false,
  alt = false,
}: KeyboardShortcutOptions) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      const keyMatches =
        event.key.toLowerCase() === key.toLowerCase() || event.key === key;

      if (!keyMatches) return;

      if (meta && !event.metaKey && !event.ctrlKey) return;
      if (ctrl && !event.ctrlKey) return;
      if (shift && !event.shiftKey) return;
      if (alt && !event.altKey) return;

      if (!meta && !ctrl && !shift && !alt) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
      }

      if (preventDefault) {
        event.preventDefault();
      }

      onKeyDown(event);
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [key, onKeyDown, enabled, preventDefault, meta, ctrl, shift, alt]);
}
