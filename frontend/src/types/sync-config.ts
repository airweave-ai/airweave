/**
 * Sync configuration matching backend SyncConfig schema
 * @see backend/airweave/platform/sync/config/base.py
 */

export interface DestinationConfig {
    skip_vespa?: boolean;
    target_destinations?: string[] | null;
    exclude_destinations?: string[] | null;
}

export interface HandlerConfig {
    enable_vector_handlers?: boolean;
    enable_raw_data_handler?: boolean;
    enable_postgres_handler?: boolean;
}

export interface CursorConfig {
    skip_load?: boolean;
    skip_updates?: boolean;
}

export interface BehaviorConfig {
    skip_hash_comparison?: boolean;
    replay_from_arf?: boolean;
    skip_guardrails?: boolean;
}

export interface SyncConfig {
    destinations?: DestinationConfig;
    handlers?: HandlerConfig;
    cursor?: CursorConfig;
    behavior?: BehaviorConfig;
}

/**
 * Preset configurations matching backend factory methods
 */
export type SyncPreset = 'default' | 'arf_capture_only' | 'replay_from_arf' | 'vespa_only' | 'custom';

export interface PresetDefinition {
    id: SyncPreset;
    label: string;
    description: string;
    config: SyncConfig;
}

export const SYNC_PRESETS: PresetDefinition[] = [
    {
        id: 'default',
        label: 'Default (Normal Sync)',
        description: 'Standard sync to Vespa with all handlers enabled',
        config: {
            destinations: { skip_vespa: false },
            handlers: { enable_vector_handlers: true, enable_raw_data_handler: true, enable_postgres_handler: true },
            cursor: { skip_load: false, skip_updates: false },
            behavior: { skip_hash_comparison: false, replay_from_arf: false },
        },
    },
    {
        id: 'arf_capture_only',
        label: 'ARF Capture Only',
        description: 'Capture raw data to ARF storage without vector DBs or postgres',
        config: {
            handlers: { enable_vector_handlers: false, enable_postgres_handler: false, enable_raw_data_handler: true },
            cursor: { skip_load: true, skip_updates: true },
            behavior: { skip_hash_comparison: true, replay_from_arf: false },
        },
    },
    {
        id: 'replay_from_arf',
        label: 'ARF Replay to Vector DBs',
        description: 'Replay from ARF storage to vector DBs (no source call)',
        config: {
            handlers: { enable_vector_handlers: true, enable_raw_data_handler: false, enable_postgres_handler: false },
            cursor: { skip_load: true, skip_updates: true },
            behavior: { skip_hash_comparison: true, replay_from_arf: true },
        },
    },
    {
        id: 'vespa_only',
        label: 'Vespa Only',
        description: 'Sync to Vespa only (default destination)',
        config: {
            destinations: { skip_vespa: false },
        },
    },
    {
        id: 'custom',
        label: 'Custom Configuration',
        description: 'Manually configure all options',
        config: {},
    },
];

/**
 * Deep merge helper for config overrides
 */
export function mergeSyncConfig(base: SyncConfig, overrides: Partial<SyncConfig>): SyncConfig {
    return {
        destinations: { ...base.destinations, ...overrides.destinations },
        handlers: { ...base.handlers, ...overrides.handlers },
        cursor: { ...base.cursor, ...overrides.cursor },
        behavior: { ...base.behavior, ...overrides.behavior },
    };
}

/**
 * Get preset config by ID
 */
export function getPresetConfig(presetId: SyncPreset): SyncConfig {
    const preset = SYNC_PRESETS.find(p => p.id === presetId);
    return preset?.config || SYNC_PRESETS[0].config;
}

