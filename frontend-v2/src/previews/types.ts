import type { ReactNode } from "react";

export interface VariantPreviewConfig {
  title: string;
  description?: string;
  preview: ReactNode;
  code: string;
}

export interface ComponentPreviewConfig {
  variants: VariantPreviewConfig[];
}

export type PreviewRegistry = Record<string, ComponentPreviewConfig>;
