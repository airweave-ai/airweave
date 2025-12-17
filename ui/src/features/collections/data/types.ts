export interface Collection {
  id: string
  name: string
  domain: string
  status: 'active' | 'syncing' | 'paused'
  sources: string[]
  lastSynced: string
  createdAt: string
  entities: number
  size: number
}
