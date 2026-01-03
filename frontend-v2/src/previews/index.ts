import { alertDialogPreview } from "./alert-dialog";
import { avatarPreview } from "./avatar";
import { badgePreview } from "./badge";
import { buttonPreview } from "./button";
import { cardPreview } from "./card";
import { checkboxPreview } from "./checkbox";
import { commandPreview } from "./command";
import { dialogPreview } from "./dialog";
import { dropdownMenuPreview } from "./dropdown-menu";
import { emptyStatePreview } from "./empty-state";
import { errorStatePreview } from "./error-state";
import { inputPreview } from "./input";
import { loadingStatePreview } from "./loading-state";
import { separatorPreview } from "./separator";
import { sheetPreview } from "./sheet";
import { skeletonPreview } from "./skeleton";
import { tablePreview } from "./table";
import { tabsPreview } from "./tabs";
import { tooltipPreview } from "./tooltip";
import type { PreviewRegistry } from "./types";

export type {
  ComponentPreviewConfig,
  PreviewRegistry,
  VariantPreviewConfig,
} from "./types";

export const componentPreviews: PreviewRegistry = {
  "alert-dialog": alertDialogPreview,
  avatar: avatarPreview,
  badge: badgePreview,
  button: buttonPreview,
  card: cardPreview,
  checkbox: checkboxPreview,
  command: commandPreview,
  dialog: dialogPreview,
  "dropdown-menu": dropdownMenuPreview,
  "empty-state": emptyStatePreview,
  "error-state": errorStatePreview,
  input: inputPreview,
  "loading-state": loadingStatePreview,
  separator: separatorPreview,
  sheet: sheetPreview,
  skeleton: skeletonPreview,
  table: tablePreview,
  tabs: tabsPreview,
  tooltip: tooltipPreview,
};
