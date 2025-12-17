export interface SourceConnection {
  name: string
  slug: string
  connected: boolean
}

export interface EntityType {
  name: string
  count: number
}

export interface Collection {
  id: string
  name: string
  status: 'active' | 'syncing' | 'paused'
  sources: SourceConnection[]
  schedule: string
  lastSync: string
  entities: {
    total: number
    types: EntityType[]
  }
}

export type MessageType = {
  key: string
  from: 'user' | 'assistant'
  content: string
}

export interface Model {
  id: string
  name: string
  provider: string
}
