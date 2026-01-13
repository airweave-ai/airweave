import { useState } from "react";
import { apiClient } from "../lib/api";
import type { Source } from "../lib/types";
import { AppIcon } from "./AppIcon";
import { BackButton } from "./BackButton";
import { Button } from "./Button";
import { FolderTree } from "./FolderTree";
import { PoweredByAirweave } from "./PoweredByAirweave";

interface FolderSelectionViewProps {
  source: Source;
  connectionId: string;
  onBack: () => void;
  onComplete: () => void;
}

export function FolderSelectionView({
  source,
  connectionId,
  onBack,
  onComplete,
}: FolderSelectionViewProps) {
  const [selectedFolderIds, setSelectedFolderIds] = useState<string[]>([]);

  const handleBack = () => {
    apiClient.deleteSourceConnection(connectionId).catch(() => {});
    onBack();
  };

  const handleStartSync = () => {
    onComplete();
  };

  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      <header className="flex-shrink-0 p-6 pb-4">
        <div className="flex items-center gap-2">
          <BackButton onClick={handleBack} />
          <AppIcon
            shortName={source.short_name}
            name={source.name}
            className="size-5"
          />
          <h1
            className="font-medium text-lg"
            style={{
              color: "var(--connect-text)",
              fontFamily: "var(--connect-font-heading)",
            }}
          >
            Select folders to sync
          </h1>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 scrollable-content">
        <FolderTree
          selectedFolderIds={selectedFolderIds}
          onSelectionChange={setSelectedFolderIds}
        />
        <div className="h-20" />
      </main>

      <div
        className="flex-shrink-0 px-6 pt-4 border-t"
        style={{
          backgroundColor: "var(--connect-bg)",
          borderColor: "var(--connect-border)",
        }}
      >
        <Button
          onClick={handleStartSync}
          disabled={selectedFolderIds.length === 0}
          className="w-full justify-center"
        >
          Start sync
          {selectedFolderIds.length > 0 &&
            ` (${selectedFolderIds.length} ${selectedFolderIds.length === 1 ? "folder" : "folders"})`}
        </Button>
      </div>

      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
