export type TimeRange = 'last_hour' | 'last_24h' | 'last_7d' | 'last_30d'

export interface DashboardMetrics {
  queries: { value: number; change: number; trend: 'up' | 'down' }
  documentsSynced: { value: number; collections: number }
  activeSyncs: { value: number; completingSoon: number }
  errors: { value: number; needsAttention: boolean }
}

export interface QueryVolumeData {
  time: string
  queries: number
}

export interface SyncActivityData {
  time: string
  documents: number
  sources: number
}

export interface FailedSync {
  id: string
  source: string
  sourceName: string
  collection: string
  error: string
  time: string
}

export interface PendingAuth {
  id: string
  source: string
  sourceName: string
  account: string
  collection: string
}

export interface TopCollection {
  id: string
  name: string
  queries: number
  entities: number
  status: 'active' | 'syncing'
}

export interface RecentConnection {
  id: string
  source: string
  sourceName: string
  account: string
  status: 'active' | 'syncing' | 'error'
  lastSynced: string
}
