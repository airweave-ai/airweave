import { Collapsible } from "@base-ui/react/collapsible";
import {
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  MinusSquare,
  Square,
} from "lucide-react";
import { useCallback, useState } from "react";

interface FolderNode {
  id: string;
  name: string;
  children?: FolderNode[];
}

const DEMO_FOLDERS: FolderNode[] = [
  {
    id: "documents",
    name: "Documents",
    children: [
      { id: "documents-work", name: "Work" },
      { id: "documents-personal", name: "Personal" },
    ],
  },
  {
    id: "projects",
    name: "Projects",
    children: [
      { id: "projects-webapp", name: "Web App" },
      {
        id: "projects-mobile",
        name: "Mobile App",
        children: [
          { id: "projects-mobile-ios", name: "iOS" },
          { id: "projects-mobile-android", name: "Android" },
        ],
      },
    ],
  },
];

// Get all descendant IDs of a folder (including itself)
function getAllDescendantIds(folder: FolderNode): string[] {
  const ids = [folder.id];
  if (folder.children) {
    for (const child of folder.children) {
      ids.push(...getAllDescendantIds(child));
    }
  }
  return ids;
}

// Get all folder IDs in the tree
function getAllFolderIds(folders: FolderNode[]): string[] {
  const ids: string[] = [];
  for (const folder of folders) {
    ids.push(...getAllDescendantIds(folder));
  }
  return ids;
}

// Check selection state: 'all' | 'some' | 'none'
function getSelectionState(
  folder: FolderNode,
  selectedIds: string[]
): "all" | "some" | "none" {
  const descendantIds = getAllDescendantIds(folder);
  const selectedCount = descendantIds.filter((id) => selectedIds.includes(id)).length;

  if (selectedCount === 0) return "none";
  if (selectedCount === descendantIds.length) return "all";
  return "some";
}

interface FolderTreeProps {
  selectedFolderIds: string[];
  onSelectionChange: (folderIds: string[]) => void;
}

interface FolderItemProps {
  folder: FolderNode;
  depth: number;
  selectedFolderIds: string[];
  onToggleFolder: (folder: FolderNode) => void;
}

function FolderItem({
  folder,
  depth,
  selectedFolderIds,
  onToggleFolder,
}: FolderItemProps) {
  const [isOpen, setIsOpen] = useState(false);
  const hasChildren = folder.children && folder.children.length > 0;
  const selectionState = getSelectionState(folder, selectedFolderIds);
  const isSelected = selectionState === "all";
  const isIndeterminate = selectionState === "some";

  const handleClick = () => {
    onToggleFolder(folder);
  };

  const CheckIcon = isSelected
    ? CheckSquare
    : isIndeterminate
      ? MinusSquare
      : Square;

  // Extra padding for folders without children to align with folders that have chevrons
  const chevronSpace = 22; // chevron width (~14px) + padding

  const content = (
    <button
      type="button"
      onClick={handleClick}
      className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm transition-colors"
      style={{
        paddingLeft: `${depth * 16 + 8 + chevronSpace}px`,
        backgroundColor: isSelected
          ? "color-mix(in srgb, var(--connect-primary) 20%, transparent)"
          : "transparent",
        color: isSelected ? "var(--connect-primary)" : "var(--connect-text)",
      }}
    >
      <CheckIcon
        size={16}
        style={{
          color:
            isSelected || isIndeterminate
              ? "var(--connect-primary)"
              : "var(--connect-text-muted)",
        }}
      />
      {hasChildren ? (
        isOpen ? (
          <FolderOpen size={16} />
        ) : (
          <Folder size={16} />
        )
      ) : (
        <Folder size={16} />
      )}
      <span className="flex-1 text-left">{folder.name}</span>
    </button>
  );

  if (!hasChildren) {
    return content;
  }

  return (
    <Collapsible.Root open={isOpen} onOpenChange={setIsOpen}>
      <div
        className="flex items-center"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        <Collapsible.Trigger
          className="p-1 rounded transition-colors hover:bg-black/10 dark:hover:bg-white/10 -ml-2"
          style={{ color: "var(--connect-text-muted)" }}
        >
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </Collapsible.Trigger>
        <button
          type="button"
          onClick={handleClick}
          className="flex items-center gap-2 flex-1 px-2 py-1.5 rounded text-sm transition-colors"
          style={{
            backgroundColor: isSelected
              ? "color-mix(in srgb, var(--connect-primary) 20%, transparent)"
              : "transparent",
            color: isSelected ? "var(--connect-primary)" : "var(--connect-text)",
          }}
        >
          <CheckIcon
            size={16}
            style={{
              color:
                isSelected || isIndeterminate
                  ? "var(--connect-primary)"
                  : "var(--connect-text-muted)",
            }}
          />
          {isOpen ? <FolderOpen size={16} /> : <Folder size={16} />}
          <span className="flex-1 text-left">{folder.name}</span>
        </button>
      </div>
      <Collapsible.Panel>
        {folder.children?.map((child) => (
          <FolderItem
            key={child.id}
            folder={child}
            depth={depth + 1}
            selectedFolderIds={selectedFolderIds}
            onToggleFolder={onToggleFolder}
          />
        ))}
      </Collapsible.Panel>
    </Collapsible.Root>
  );
}

export function FolderTree({
  selectedFolderIds,
  onSelectionChange,
}: FolderTreeProps) {
  const allFolderIds = getAllFolderIds(DEMO_FOLDERS);
  
  // Compute root selection state from children (not from "root" in selectedFolderIds)
  const selectedChildCount = allFolderIds.filter((id) =>
    selectedFolderIds.includes(id)
  ).length;
  const isRootSelected = selectedChildCount === allFolderIds.length && allFolderIds.length > 0;
  const isRootIndeterminate = selectedChildCount > 0 && selectedChildCount < allFolderIds.length;
  
  const CheckIcon = isRootSelected
    ? CheckSquare
    : isRootIndeterminate
      ? MinusSquare
      : Square;

  const handleToggleFolder = useCallback(
    (folder: FolderNode) => {
      const descendantIds = getAllDescendantIds(folder);
      const isCurrentlySelected = selectedFolderIds.includes(folder.id);

      if (isCurrentlySelected) {
        // Deselect this folder and all its descendants
        onSelectionChange(
          selectedFolderIds.filter((id) => !descendantIds.includes(id)),
        );
      } else {
        // Select this folder and all its descendants
        const newSelection = new Set([...selectedFolderIds, ...descendantIds]);
        onSelectionChange([...newSelection]);
      }
    },
    [selectedFolderIds, onSelectionChange],
  );

  const handleToggleRoot = useCallback(() => {
    if (isRootSelected) {
      // Deselect all folders
      onSelectionChange([]);
    } else {
      // Select all folders (root state is computed, not stored)
      onSelectionChange([...allFolderIds]);
    }
  }, [isRootSelected, allFolderIds, onSelectionChange]);

  return (
    <div className="flex flex-col">
      {/* Root folder option */}
      <button
        type="button"
        onClick={handleToggleRoot}
        className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm transition-colors mb-1"
        style={{
          backgroundColor: isRootSelected
            ? "color-mix(in srgb, var(--connect-primary) 20%, transparent)"
            : "transparent",
          color: isRootSelected ? "var(--connect-primary)" : "var(--connect-text)",
        }}
      >
        <CheckIcon
          size={16}
          style={{
            color:
              isRootSelected || isRootIndeterminate
                ? "var(--connect-primary)"
                : "var(--connect-text-muted)",
          }}
        />
        <Folder size={16} />
        <span className="flex-1 text-left font-medium">/ (Root)</span>
      </button>

      {/* Subfolders */}
      {DEMO_FOLDERS.map((folder) => (
        <FolderItem
          key={folder.id}
          folder={folder}
          depth={0}
          selectedFolderIds={selectedFolderIds}
          onToggleFolder={handleToggleFolder}
        />
      ))}
    </div>
  );
}
