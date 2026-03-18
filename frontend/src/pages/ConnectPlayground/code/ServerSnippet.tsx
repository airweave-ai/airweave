import { useMemo } from "react";
import { SnippetFrame } from "./SnippetFrame";
import { generatePythonServer, generateTypeScriptServer } from "./codeGen";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface ServerSnippetProps {
  config: PlaygroundConfig;
  isNewCollection?: boolean;
  stepNumber?: number;
  description?: string;
}

export function ServerSnippet({ config, isNewCollection = false, stepNumber, description }: ServerSnippetProps) {
  const tabs = useMemo(
    () => [
      { id: "python", label: "Python", language: "python", code: generatePythonServer(config, isNewCollection) },
      { id: "typescript", label: "TypeScript", language: "typescript", code: generateTypeScriptServer(config, isNewCollection) },
    ],
    [config, isNewCollection]
  );

  return <SnippetFrame label="Server" tabs={tabs} stepNumber={stepNumber} description={description} />;
}
