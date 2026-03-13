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
import {
  getAllDescendantIds,
  getAllFolderIds,
  getRootSelectionState,
  getSelectionState,
  type FolderNode,
  type SelectionState,
} from "../lib/folder-utils";

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

function SelectionCheckIcon({
  state,
  size,
  style,
}: {
  state: SelectionState;
  size: number;
  style?: React.CSSProperties;
}) {
  if (state === "all") return <CheckSquare size={size} style={style} />;
  if (state === "some") return <MinusSquare size={size} style={style} />;
  return <Square size={size} style={style} />;
}

function getButtonStyle(isSelected: boolean) {
  return {
    backgroundColor: isSelected
      ? "color-mix(in srgb, var(--connect-primary) 20%, transparent)"
      : "transparent",
    color: isSelected ? "var(--connect-primary)" : "var(--connect-text)",
  };
}

function getCheckIconStyle(isHighlighted: boolean) {
  return {
    color: isHighlighted
      ? "var(--connect-primary)"
      : "var(--connect-text-muted)",
  };
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

interface FolderButtonContentProps {
  name: string;
  isOpen: boolean;
  hasChildren: boolean;
  selectionState: SelectionState;
}

function FolderButtonContent({
  name,
  isOpen,
  hasChildren,
  selectionState,
}: FolderButtonContentProps) {
  const isHighlighted = selectionState !== "none";

  return (
    <>
      <SelectionCheckIcon
        state={selectionState}
        size={16}
        style={getCheckIconStyle(isHighlighted)}
      />
      {hasChildren && isOpen ? <FolderOpen size={16} /> : <Folder size={16} />}
      <span className="flex-1 text-left">{name}</span>
    </>
  );
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

  const handleClick = () => onToggleFolder(folder);

  const buttonStyle = getButtonStyle(isSelected);
  const chevronSpace = 22;

  if (!hasChildren) {
    return (
      <button
        type="button"
        onClick={handleClick}
        className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm transition-colors"
        style={{
          paddingLeft: `${depth * 16 + 8 + chevronSpace}px`,
          ...buttonStyle,
        }}
      >
        <FolderButtonContent
          name={folder.name}
          isOpen={false}
          hasChildren={false}
          selectionState={selectionState}
        />
      </button>
    );
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
          style={buttonStyle}
        >
          <FolderButtonContent
            name={folder.name}
            isOpen={isOpen}
            hasChildren={true}
            selectionState={selectionState}
          />
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
  const rootSelectionState = getRootSelectionState(
    allFolderIds,
    selectedFolderIds,
  );
  const isRootSelected = rootSelectionState === "all";

  const handleToggleFolder = useCallback(
    (folder: FolderNode) => {
      const descendantIds = getAllDescendantIds(folder);
      const isCurrentlySelected = selectedFolderIds.includes(folder.id);

      if (isCurrentlySelected) {
        onSelectionChange(
          selectedFolderIds.filter((id) => !descendantIds.includes(id)),
        );
      } else {
        const newSelection = new Set([...selectedFolderIds, ...descendantIds]);
        onSelectionChange([...newSelection]);
      }
    },
    [selectedFolderIds, onSelectionChange],
  );

  const handleToggleRoot = useCallback(() => {
    onSelectionChange(isRootSelected ? [] : [...allFolderIds]);
  }, [isRootSelected, allFolderIds, onSelectionChange]);

  return (
    <div className="flex flex-col">
      <button
        type="button"
        onClick={handleToggleRoot}
        className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm transition-colors mb-1"
        style={getButtonStyle(isRootSelected)}
      >
        <SelectionCheckIcon
          state={rootSelectionState}
          size={16}
          style={getCheckIconStyle(rootSelectionState !== "none")}
        />
        <Folder size={16} />
        <span className="flex-1 text-left font-medium">/ (Root)</span>
      </button>

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
