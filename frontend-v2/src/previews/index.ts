import { alertDialogPreview } from "./alert-dialog";
import { buttonPreview } from "./button";
import { inputPreview } from "./input";
import { separatorPreview } from "./separator";
import { sheetPreview } from "./sheet";
import { skeletonPreview } from "./skeleton";
import { tooltipPreview } from "./tooltip";
import type { PreviewRegistry } from "./types";

export type {
  ComponentPreviewConfig,
  PreviewRegistry,
  VariantPreviewConfig,
} from "./types";

export const componentPreviews: PreviewRegistry = {
  "alert-dialog": alertDialogPreview,
  button: buttonPreview,
  input: inputPreview,
  separator: separatorPreview,
  sheet: sheetPreview,
  skeleton: skeletonPreview,
  tooltip: tooltipPreview,
};
