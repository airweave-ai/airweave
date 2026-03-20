import { ServerSnippet } from "./ServerSnippet";
import { ClientSnippet } from "./ClientSnippet";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface CodePreviewProps {
  config: PlaygroundConfig;
  isNewCollection?: boolean;
}

export function CodePreview({ config, isNewCollection = false }: CodePreviewProps) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <ServerSnippet
          config={config}
          isNewCollection={isNewCollection}
          description="Create a session endpoint that returns a token to your frontend"
        />
      </div>
      <div>
        <ClientSnippet
          config={config}
          description="Use the SDK to open the Connect widget with the session token"
        />
      </div>
    </div>
  );
}
