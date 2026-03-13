import { describe, expect, it } from "vitest";
import {
  getAllDescendantIds,
  getAllFolderIds,
  getSelectionState,
  getRootSelectionState,
  type FolderNode,
} from "./folder-utils";

describe("folder-utils", () => {
  const singleFolder: FolderNode = {
    id: "folder-1",
    name: "Folder 1",
  };

  const nestedFolder: FolderNode = {
    id: "parent",
    name: "Parent",
    children: [
      { id: "child-1", name: "Child 1" },
      {
        id: "child-2",
        name: "Child 2",
        children: [
          { id: "grandchild-1", name: "Grandchild 1" },
          { id: "grandchild-2", name: "Grandchild 2" },
        ],
      },
    ],
  };

  const multipleFolders: FolderNode[] = [
    { id: "root-1", name: "Root 1" },
    {
      id: "root-2",
      name: "Root 2",
      children: [{ id: "root-2-child", name: "Root 2 Child" }],
    },
  ];

  describe("getAllDescendantIds", () => {
    it("returns single ID for folder without children", () => {
      const result = getAllDescendantIds(singleFolder);
      expect(result).toEqual(["folder-1"]);
    });

    it("returns all nested IDs for folder with children", () => {
      const result = getAllDescendantIds(nestedFolder);
      expect(result).toEqual([
        "parent",
        "child-1",
        "child-2",
        "grandchild-1",
        "grandchild-2",
      ]);
    });

    it("returns IDs in depth-first order", () => {
      const result = getAllDescendantIds(nestedFolder);
      expect(result.indexOf("parent")).toBeLessThan(result.indexOf("child-1"));
      expect(result.indexOf("child-2")).toBeLessThan(
        result.indexOf("grandchild-1"),
      );
    });
  });

  describe("getAllFolderIds", () => {
    it("returns empty array for empty input", () => {
      const result = getAllFolderIds([]);
      expect(result).toEqual([]);
    });

    it("returns all IDs from multiple root folders", () => {
      const result = getAllFolderIds(multipleFolders);
      expect(result).toEqual(["root-1", "root-2", "root-2-child"]);
    });

    it("handles single folder in array", () => {
      const result = getAllFolderIds([singleFolder]);
      expect(result).toEqual(["folder-1"]);
    });
  });

  describe("getSelectionState", () => {
    it("returns 'none' when no descendants are selected", () => {
      const result = getSelectionState(nestedFolder, []);
      expect(result).toBe("none");
    });

    it("returns 'none' when unrelated IDs are selected", () => {
      const result = getSelectionState(nestedFolder, ["unrelated-id"]);
      expect(result).toBe("none");
    });

    it("returns 'all' when all descendants are selected", () => {
      const allIds = getAllDescendantIds(nestedFolder);
      const result = getSelectionState(nestedFolder, allIds);
      expect(result).toBe("all");
    });

    it("returns 'some' when only some descendants are selected", () => {
      const result = getSelectionState(nestedFolder, ["parent", "child-1"]);
      expect(result).toBe("some");
    });

    it("returns 'all' for leaf folder when it is selected", () => {
      const result = getSelectionState(singleFolder, ["folder-1"]);
      expect(result).toBe("all");
    });
  });

  describe("getRootSelectionState", () => {
    const allFolderIds = ["id-1", "id-2", "id-3"];

    it("returns 'none' when no folders are selected", () => {
      const result = getRootSelectionState(allFolderIds, []);
      expect(result).toBe("none");
    });

    it("returns 'all' when all folders are selected", () => {
      const result = getRootSelectionState(allFolderIds, allFolderIds);
      expect(result).toBe("all");
    });

    it("returns 'some' when some folders are selected", () => {
      const result = getRootSelectionState(allFolderIds, ["id-1", "id-2"]);
      expect(result).toBe("some");
    });

    it("returns 'none' for empty folder list with empty selection", () => {
      const result = getRootSelectionState([], []);
      expect(result).toBe("none");
    });

    it("returns 'some' for empty folder list with non-empty selection", () => {
      // Edge case: selected IDs that don't exist in allFolderIds
      const result = getRootSelectionState([], ["some-id"]);
      expect(result).toBe("none");
    });

    it("handles selection with extra IDs not in folder list", () => {
      const result = getRootSelectionState(allFolderIds, [
        "id-1",
        "extra-id",
        "id-2",
      ]);
      expect(result).toBe("some");
    });
  });
});
