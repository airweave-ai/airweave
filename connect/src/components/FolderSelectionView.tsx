import { useState } from "react";
import { apiClient } from "../lib/api";
import { useTheme } from "../lib/theme";
import type { Source } from "../lib/types";
import { AppIcon } from "./AppIcon";
import { BackButton } from "./BackButton";
import { Button } from "./Button";
import { FolderTree } from "./FolderTree";
import { PageLayout } from "./PageLayout";

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
  const { labels } = useTheme();
  const [selectedFolderIds, setSelectedFolderIds] = useState<string[]>([]);

  const handleBack = () => {
    apiClient.deleteSourceConnection(connectionId).catch(() => {});
    onBack();
  };

  const buttonLabel =
    selectedFolderIds.length > 0
      ? `${labels.folderSelectionStartSync} (${labels.folderSelectionCount.replace("{count}", String(selectedFolderIds.length))})`
      : labels.folderSelectionStartSync;

  const headerLeft = (
    <div className="flex items-center gap-2">
      <BackButton onClick={handleBack} />
      <AppIcon shortName={source.short_name} name={source.name} className="size-5" />
    </div>
  );

  const footerContent = (
    <Button
      onClick={onComplete}
      disabled={selectedFolderIds.length === 0}
      className="w-full justify-center"
    >
      {buttonLabel}
    </Button>
  );

  return (
    <PageLayout
      title={labels.folderSelectionHeading}
      headerLeft={headerLeft}
      footerContent={footerContent}
    >
      <FolderTree
        selectedFolderIds={selectedFolderIds}
        onSelectionChange={setSelectedFolderIds}
      />
      <div className="h-20" />
    </PageLayout>
  );
}
