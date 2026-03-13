import { useMemo } from "react";
import { SnippetFrame } from "./SnippetFrame";
import { generateReactClient, generateVanillaClient } from "./codeGen";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface ClientSnippetProps {
  config: PlaygroundConfig;
}

export function ClientSnippet({ config }: ClientSnippetProps) {
  const tabs = useMemo(
    () => [
      { id: "react", label: "React", code: generateReactClient(config) },
      { id: "vanilla", label: "Vanilla JS", code: generateVanillaClient(config) },
    ],
    [config]
  );

  return <SnippetFrame label="Client" tabs={tabs} />;
}
