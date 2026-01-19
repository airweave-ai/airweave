/**
 * Shared navigation state types for router state passing
 */

import type { PreSelectedSource } from "@/stores/create-collection-store";

/**
 * Navigation state for the "Start from a Source" flow
 * Used when navigating to a collection page with a pre-selected source
 */
export interface CollectionNavigationState {
  addSource?: PreSelectedSource;
}
