import { useMemo } from "react";
import { SnippetFrame } from "./SnippetFrame";
import { generateReactClient, generateVanillaClient } from "./codeGen";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface ClientSnippetProps {
  config: PlaygroundConfig;
  stepNumber?: number;
  description?: string;
}

export function ClientSnippet({ config, stepNumber, description }: ClientSnippetProps) {
  const tabs = useMemo(
    () => [
      { id: "react", label: "React", language: "jsx", code: generateReactClient(config) },
      { id: "vanilla", label: "Vanilla JS", language: "javascript", code: generateVanillaClient(config) },
    ],
    [config]
  );

  return <SnippetFrame label="Client" tabs={tabs} stepNumber={stepNumber} description={description} />;
}
