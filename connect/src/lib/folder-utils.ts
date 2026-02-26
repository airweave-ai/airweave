export interface FolderNode {
  id: string;
  name: string;
  children?: FolderNode[];
}

export type SelectionState = "all" | "some" | "none";

export function getAllDescendantIds(folder: FolderNode): string[] {
  const ids = [folder.id];
  if (folder.children) {
    for (const child of folder.children) {
      ids.push(...getAllDescendantIds(child));
    }
  }
  return ids;
}

export function getAllFolderIds(folders: FolderNode[]): string[] {
  const ids: string[] = [];
  for (const folder of folders) {
    ids.push(...getAllDescendantIds(folder));
  }
  return ids;
}

export function getSelectionState(
  folder: FolderNode,
  selectedIds: string[],
): SelectionState {
  const descendantIds = getAllDescendantIds(folder);
  const selectedCount = descendantIds.filter((id) =>
    selectedIds.includes(id),
  ).length;

  if (selectedCount === 0) return "none";
  if (selectedCount === descendantIds.length) return "all";
  return "some";
}

export function getRootSelectionState(
  allFolderIds: string[],
  selectedFolderIds: string[],
): SelectionState {
  const selectedCount = allFolderIds.filter((id) =>
    selectedFolderIds.includes(id),
  ).length;

  if (selectedCount === 0) return "none";
  if (selectedCount === allFolderIds.length && allFolderIds.length > 0)
    return "all";
  return "some";
}
