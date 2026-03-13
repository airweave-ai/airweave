import { useEffect, useRef, useCallback } from "react";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface UseIframeBridgeOptions {
  sessionToken: string | null;
  config: PlaygroundConfig;
  isOpen: boolean;
}

export function useIframeBridge({ sessionToken, config, isOpen }: UseIframeBridgeOptions) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

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
    if (!isOpen) return;

    const handler = (e: MessageEvent) => {
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
          "*"
        );
      }
    };

    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [isOpen, sessionToken, buildThemePayload]);

  // Push theme updates to the iframe in real-time
  useEffect(() => {
    if (!isOpen || !iframeRef.current?.contentWindow) return;

    iframeRef.current.contentWindow.postMessage(
      { type: "SET_THEME", theme: buildThemePayload() },
      "*"
    );
  }, [isOpen, buildThemePayload]);

  return { iframeRef };
}
