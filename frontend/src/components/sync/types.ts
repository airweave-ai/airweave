import { z } from "zod"; // We'll use zod for runtime validation if needed

export interface SyncBase {
  name: string;
  description?: string | null;
  sourceConnectionId: string; // UUID
  destinationConnectionId?: string | null; // UUID
  embeddingModelConnectionId?: string | null; // UUID
  cronSchedule?: string | null;
  whiteLabelId?: string | null; // UUID
  whiteLabelUserIdentifier?: string | null;
  syncMetadata?: Record<string, any> | null;
}

export interface SyncCreate extends SyncBase {
  runImmediately?: boolean;
}

export interface SyncUpdate {
  name?: string;
  schedule?: string;
  sourceConnectionId?: string;
  destinationConnectionId?: string;
  embeddingModelConnectionId?: string;
  cronSchedule?: string;
  whiteLabelId?: string;
  whiteLabelUserIdentifier?: string;
  syncMetadata?: Record<string, any>;
}

export interface SyncInDB extends SyncBase {
  id: string; // UUID
  organizationId: string; // UUID
  createdAt: string; // ISO datetime
  modifiedAt: string; // ISO datetime
  createdByEmail: string;
  modifiedByEmail: string;
}

// This is the main interface we'll use in our components
export interface Sync extends SyncInDB {}

// Optional: Zod schema for runtime validation
export const syncSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable().optional(),
  sourceConnectionId: z.string().uuid(),
  destinationConnectionId: z.string().uuid().nullable().optional(),
  embeddingModelConnectionId: z.string().uuid().nullable().optional(),
  cronSchedule: z.string().nullable().optional(),
  whiteLabelId: z.string().uuid().nullable().optional(),
  whiteLabelUserIdentifier: z.string().nullable().optional(),
  syncMetadata: z.record(z.any()).nullable().optional(),
  organizationId: z.string().uuid(),
  createdAt: z.string().datetime(),
  modifiedAt: z.string().datetime(),
  createdByEmail: z.string().email(),
  modifiedByEmail: z.string().email(),
});

// Additional interfaces for the UI components
export interface SyncSource {
  name: string;
  shortName: string;
  type: string;
}

export interface SyncDestination {
  name: string;
  shortName: string;
  type: string;
}

export interface SyncUIMetadata {
  source: SyncSource;
  destination: SyncDestination;
  userId: string;
  organizationId: string;
  userEmail: string;
}

// This interface combines the backend data with UI-specific metadata
export interface SyncDetailsData extends Sync {
  status: 'active' | 'inactive' | 'error';
  totalRuns?: number;
  uiMetadata: SyncUIMetadata;
}
