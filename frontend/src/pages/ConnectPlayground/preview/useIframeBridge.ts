import { useEffect, useRef, useCallback, useMemo } from "react";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface UseIframeBridgeOptions {
  sessionToken: string | null;
  config: PlaygroundConfig;
  isOpen: boolean;
  connectUrl: string;
}

export function useIframeBridge({ sessionToken, config, isOpen, connectUrl }: UseIframeBridgeOptions) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const targetOrigin = useMemo(() => {
    try { return new URL(connectUrl).origin; }
    catch { return ""; }
  }, [connectUrl]);

  const buildThemePayload = useCallback(() => {
    const theme: Record<string, unknown> = {
      mode: config.themeMode,
      colors: {
        dark: config.darkColors,
        light: config.lightColors,
      },
    };
    if (config.logoUrl) {
      theme.options = { logoUrl: config.logoUrl };
    }
    return theme;
  }, [config.themeMode, config.darkColors, config.lightColors, config.logoUrl]);

  // Respond to token requests from the iframe
  useEffect(() => {
    if (!isOpen || !targetOrigin) return;

    const handler = (e: MessageEvent) => {
      if (e.origin !== targetOrigin) return;

      const { data } = e;
      if (!data || typeof data !== "object" || !data.type) return;

      if (data.type === "REQUEST_TOKEN" && sessionToken) {
        iframeRef.current?.contentWindow?.postMessage(
          {
            type: "TOKEN_RESPONSE",
            requestId: data.requestId,
            token: sessionToken,
            theme: buildThemePayload(),
          },
          targetOrigin
        );
      }
    };

    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [isOpen, sessionToken, buildThemePayload, targetOrigin]);

  // Push theme updates to the iframe in real-time
  useEffect(() => {
    if (!isOpen || !targetOrigin || !iframeRef.current?.contentWindow) return;

    iframeRef.current.contentWindow.postMessage(
      { type: "SET_THEME", theme: buildThemePayload() },
      targetOrigin
    );
  }, [isOpen, buildThemePayload, targetOrigin]);

  return { iframeRef };
}
