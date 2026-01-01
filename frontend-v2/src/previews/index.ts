import { alertDialogPreview } from "./alert-dialog";
import { buttonPreview } from "./button";
import type { PreviewRegistry } from "./types";

export type {
  ComponentPreviewConfig,
  PreviewRegistry,
  VariantPreviewConfig,
} from "./types";

export const componentPreviews: PreviewRegistry = {
  "alert-dialog": alertDialogPreview,
  button: buttonPreview,
};
