import { useEffect } from "react";
function useKeyboardShortcut({
  key,
  onKeyDown,
  enabled = true,
  preventDefault = true,
  meta = false,
  ctrl = false,
  shift = false,
  alt = false
}) {
  useEffect(() => {
    if (!enabled) return;
    const handleKeyDown = (event) => {
      const keyMatches = event.key.toLowerCase() === key.toLowerCase() || event.key === key;
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
export {
  useKeyboardShortcut as u
};
