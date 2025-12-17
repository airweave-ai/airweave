export interface SourceConnection {
  id: string
  account: string
  shortName: string
  collectionId: string
  status:
    | 'active'
    | 'pending_auth'
    | 'syncing'
    | 'error'
    | 'inactive'
    | 'pending_sync'
  authMethod:
    | 'direct'
    | 'oauth_browser'
    | 'oauth_token'
    | 'oauth_byoc'
    | 'auth_provider'
  isAuthenticated: boolean
  entityCount: number
  federatedSearch: boolean
  createdAt: string
  modifiedAt: string
}
