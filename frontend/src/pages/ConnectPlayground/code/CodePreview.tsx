import { ServerSnippet } from "./ServerSnippet";
import { ClientSnippet } from "./ClientSnippet";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface CodePreviewProps {
  config: PlaygroundConfig;
  isNewCollection?: boolean;
}

export function CodePreview({ config, isNewCollection = false }: CodePreviewProps) {
  return (
    <div className="h-full flex flex-col gap-1.5">
      <div className="flex-[4] min-h-0">
        <ServerSnippet config={config} isNewCollection={isNewCollection} />
      </div>
      <div className="flex-[5] min-h-0">
        <ClientSnippet config={config} />
      </div>
    </div>
  );
}
