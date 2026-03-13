import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { useSourcesStore, useCollectionsStore } from "@/lib/stores";
import { posthog } from "@/lib/posthog-provider";

export type ThemeMode = "dark" | "light" | "system";
export type SessionMode = "all" | "connect" | "manage" | "reauth";
export type ShadowSize = "none" | "sm" | "md" | "lg" | "xl";

export interface ThemeColors {
  background: string;
  surface: string;
  primary: string;
  text: string;
  textMuted: string;
  border: string;
}

export interface ModalAppearance {
  shadow: ShadowSize;
  borderRadius: number;
  borderWidth: number;
  borderColor: string;
}

export interface PlaygroundConfig {
  themeMode: ThemeMode;
  darkColors: ThemeColors;
  lightColors: ThemeColors;
  allowedIntegrations: string[];
  sessionMode: SessionMode;
  logoUrl: string;
  modal: ModalAppearance;
}

export const DEFAULT_DARK: ThemeColors = {
  background: "#0f172a",
  surface: "#1e293b",
  primary: "#06b6d4",
  text: "#ffffff",
  textMuted: "#9ca3af",
  border: "#334155",
};

export const DEFAULT_LIGHT: ThemeColors = {
  background: "#ffffff",
  surface: "#f9fafb",
  primary: "#0891b2",
  text: "#111827",
  textMuted: "#6b7280",
  border: "#e5e7eb",
};

const INITIAL_CONFIG: PlaygroundConfig = {
  themeMode: "dark",
  darkColors: { ...DEFAULT_DARK },
  lightColors: { ...DEFAULT_LIGHT },
  allowedIntegrations: [],
  sessionMode: "all",
  logoUrl: "",
  modal: {
    shadow: "lg",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#334155",
  },
};

export function usePlaygroundState() {
  const { sources, fetchSources } = useSourcesStore();
  const { collections, fetchCollections } = useCollectionsStore();

  const [config, setConfig] = useState<PlaygroundConfig>(INITIAL_CONFIG);
  const [selectedCollection, setSelectedCollection] = useState("");
  const [isNewCollection, setIsNewCollection] = useState(false);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  useEffect(() => {
    fetchSources();
    fetchCollections();
  }, [fetchSources, fetchCollections]);

  useEffect(() => {
    if (collections.length > 0 && !selectedCollection) {
      setSelectedCollection(collections[0].readable_id);
    }
  }, [collections, selectedCollection]);

  const updateConfig = useCallback((patch: Partial<PlaygroundConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
  }, []);

  const updateModal = useCallback((patch: Partial<ModalAppearance>) => {
    setConfig((prev) => ({ ...prev, modal: { ...prev.modal, ...patch } }));
  }, []);

  const activeColors = config.themeMode === "light" ? config.lightColors : config.darkColors;
  const activeDefaults = config.themeMode === "light" ? DEFAULT_LIGHT : DEFAULT_DARK;
  const activeColorKey = config.themeMode === "light" ? "lightColors" : "darkColors";

  const setActiveColor = useCallback(
    (key: keyof ThemeColors, value: string) => {
      setConfig((prev) => ({
        ...prev,
        [prev.themeMode === "light" ? "lightColors" : "darkColors"]: {
          ...prev[prev.themeMode === "light" ? "lightColors" : "darkColors"],
          [key]: value,
        },
      }));
    },
    []
  );

  const toggleIntegration = useCallback((shortName: string) => {
    setConfig((prev) => ({
      ...prev,
      allowedIntegrations: prev.allowedIntegrations.includes(shortName)
        ? prev.allowedIntegrations.filter((s) => s !== shortName)
        : [...prev.allowedIntegrations, shortName],
    }));
  }, []);

  const createSession = useCallback(async () => {
    if (!selectedCollection && !isNewCollection) return null;
    setIsCreatingSession(true);
    try {
      let collectionId = selectedCollection;

      if (isNewCollection) {
        const colRes = await apiClient.post("/collections", {
          name: `Playground ${new Date().toLocaleDateString()}`,
        });
        if (!colRes.ok) return null;
        const col = await colRes.json();
        collectionId = col.readable_id;
        setSelectedCollection(collectionId);
        setIsNewCollection(false);
        fetchCollections();
      }

      const body: Record<string, unknown> = {
        readable_collection_id: collectionId,
        mode: config.sessionMode,
      };
      if (config.allowedIntegrations.length > 0) {
        body.allowed_integrations = config.allowedIntegrations;
      }
      const res = await apiClient.post("/connect/sessions", body);
      if (res.ok) {
        const data = await res.json();
        setSessionToken(data.session_token);
        return data.session_token as string;
      }
      return null;
    } finally {
      setIsCreatingSession(false);
    }
  }, [selectedCollection, isNewCollection, config.sessionMode, config.allowedIntegrations, fetchCollections]);

  const openPreview = useCallback(async () => {
    posthog.capture("connect_playground_preview_clicked", {
      collection_id: selectedCollection,
      mode: config.sessionMode,
      allowed_integrations_count: config.allowedIntegrations.length,
    });
    const token = await createSession();
    if (token) setIsPreviewOpen(true);
  }, [createSession, selectedCollection, config.sessionMode, config.allowedIntegrations.length]);

  const closePreview = useCallback(() => {
    setIsPreviewOpen(false);
  }, []);

  return {
    config,
    updateConfig,
    updateModal,
    activeColors,
    activeDefaults,
    activeColorKey,
    setActiveColor,
    toggleIntegration,
    sources,
    collections,
    selectedCollection,
    setSelectedCollection,
    isNewCollection,
    setIsNewCollection,
    sessionToken,
    isCreatingSession,
    isPreviewOpen,
    openPreview,
    closePreview,
    createSession,
  };
}
