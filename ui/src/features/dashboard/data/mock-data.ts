import type {
  DashboardMetrics,
  FailedSync,
  PendingAuth,
  QueryVolumeData,
  RecentConnection,
  SyncActivityData,
  TimeRange,
  TopCollection,
} from './types'

export const timeRangeLabels: Record<TimeRange, string> = {
  last_hour: 'Last hour',
  last_24h: 'Last 24 hours',
  last_7d: 'Last 7 days',
  last_30d: 'Last 30 days',
}

export const mockDataByTimeRange: Record<
  TimeRange,
  {
    metrics: DashboardMetrics
    queryVolumeChart: QueryVolumeData[]
    syncActivityChart: SyncActivityData[]
  }
> = {
  last_hour: {
    metrics: {
      queries: { value: 2893, change: 12, trend: 'up' },
      documentsSynced: { value: 1247, collections: 5 },
      activeSyncs: { value: 3, completingSoon: 2 },
      errors: { value: 2, needsAttention: true },
    },
    queryVolumeChart: [
      { time: '10:00', queries: 245 },
      { time: '10:10', queries: 312 },
      { time: '10:20', queries: 287 },
      { time: '10:30', queries: 398 },
      { time: '10:40', queries: 456 },
      { time: '10:50', queries: 521 },
      { time: '11:00', queries: 674 },
    ],
    syncActivityChart: [
      { time: '10:00', documents: 89, sources: 3 },
      { time: '10:10', documents: 156, sources: 4 },
      { time: '10:20', documents: 203, sources: 5 },
      { time: '10:30', documents: 178, sources: 4 },
      { time: '10:40', documents: 245, sources: 6 },
      { time: '10:50', documents: 189, sources: 4 },
      { time: '11:00', documents: 187, sources: 3 },
    ],
  },
  last_24h: {
    metrics: {
      queries: { value: 47832, change: 8, trend: 'up' },
      documentsSynced: { value: 23456, collections: 8 },
      activeSyncs: { value: 5, completingSoon: 3 },
      errors: { value: 4, needsAttention: true },
    },
    queryVolumeChart: [
      { time: '12 AM', queries: 1245 },
      { time: '4 AM', queries: 892 },
      { time: '8 AM', queries: 3421 },
      { time: '12 PM', queries: 5678 },
      { time: '4 PM', queries: 8934 },
      { time: '8 PM', queries: 12456 },
      { time: '11 PM', queries: 15206 },
    ],
    syncActivityChart: [
      { time: '12 AM', documents: 1890, sources: 8 },
      { time: '4 AM', documents: 2456, sources: 10 },
      { time: '8 AM', documents: 4203, sources: 12 },
      { time: '12 PM', documents: 3178, sources: 9 },
      { time: '4 PM', documents: 5245, sources: 14 },
      { time: '8 PM', documents: 3889, sources: 11 },
      { time: '11 PM', documents: 2595, sources: 8 },
    ],
  },
  last_7d: {
    metrics: {
      queries: { value: 284521, change: 23, trend: 'up' },
      documentsSynced: { value: 156789, collections: 10 },
      activeSyncs: { value: 2, completingSoon: 1 },
      errors: { value: 7, needsAttention: true },
    },
    queryVolumeChart: [
      { time: 'Mon', queries: 34521 },
      { time: 'Tue', queries: 42156 },
      { time: 'Wed', queries: 38945 },
      { time: 'Thu', queries: 45632 },
      { time: 'Fri', queries: 52341 },
      { time: 'Sat', queries: 31245 },
      { time: 'Sun', queries: 39681 },
    ],
    syncActivityChart: [
      { time: 'Mon', documents: 18903, sources: 24 },
      { time: 'Tue', documents: 24561, sources: 28 },
      { time: 'Wed', documents: 22034, sources: 26 },
      { time: 'Thu', documents: 21782, sources: 25 },
      { time: 'Fri', documents: 26451, sources: 30 },
      { time: 'Sat', documents: 19887, sources: 22 },
      { time: 'Sun', documents: 23171, sources: 24 },
    ],
  },
  last_30d: {
    metrics: {
      queries: { value: 1247893, change: -3, trend: 'down' },
      documentsSynced: { value: 687432, collections: 10 },
      activeSyncs: { value: 1, completingSoon: 0 },
      errors: { value: 12, needsAttention: true },
    },
    queryVolumeChart: [
      { time: 'Week 1', queries: 284521 },
      { time: 'Week 2', queries: 312456 },
      { time: 'Week 3', queries: 298745 },
      { time: 'Week 4', queries: 352171 },
    ],
    syncActivityChart: [
      { time: 'Week 1', documents: 156789, sources: 45 },
      { time: 'Week 2', documents: 178234, sources: 52 },
      { time: 'Week 3', documents: 165432, sources: 48 },
      { time: 'Week 4', documents: 186977, sources: 55 },
    ],
  },
}

export const needsAttention: {
  failedSyncs: FailedSync[]
  pendingAuth: PendingAuth[]
} = {
  failedSyncs: [
    {
      id: '1',
      source: 'github',
      sourceName: 'GitHub',
      collection: 'Engineering Docs',
      error: 'Rate limit exceeded',
      time: '5 min ago',
    },
    {
      id: '2',
      source: 'slackhq',
      sourceName: 'Slack',
      collection: 'Customer Support',
      error: 'Connection timeout',
      time: '23 min ago',
    },
  ],
  pendingAuth: [
    {
      id: '1',
      source: 'makenotion',
      sourceName: 'Notion',
      account: 'workspace@company.com',
      collection: 'Product Roadmap',
    },
  ],
}

export const topCollections: TopCollection[] = [
  {
    id: '1',
    name: "Anand's collection",
    queries: 1247,
    entities: 3421,
    status: 'active',
  },
  {
    id: '2',
    name: 'Engineering Docs',
    queries: 892,
    entities: 5672,
    status: 'syncing',
  },
  {
    id: '3',
    name: 'Customer Support',
    queries: 654,
    entities: 2103,
    status: 'active',
  },
  {
    id: '4',
    name: 'Marketing Assets',
    queries: 421,
    entities: 1834,
    status: 'active',
  },
  {
    id: '5',
    name: 'Sales Pipeline',
    queries: 312,
    entities: 892,
    status: 'active',
  },
]

export const recentConnections: RecentConnection[] = [
  {
    id: '1',
    source: 'github',
    sourceName: 'GitHub',
    account: 'airweave-ai',
    status: 'active',
    lastSynced: '2 min ago',
  },
  {
    id: '2',
    source: 'makenotion',
    sourceName: 'Notion',
    account: 'workspace',
    status: 'syncing',
    lastSynced: '5 min ago',
  },
  {
    id: '3',
    source: 'slackhq',
    sourceName: 'Slack',
    account: 'airweave',
    status: 'error',
    lastSynced: '1 hour ago',
  },
  {
    id: '4',
    source: 'linear',
    sourceName: 'Linear',
    account: 'airweave',
    status: 'active',
    lastSynced: '15 min ago',
  },
  {
    id: '5',
    source: 'google',
    sourceName: 'Google Drive',
    account: 'team@airweave.ai',
    status: 'active',
    lastSynced: '30 min ago',
  },
]

export const queryChartConfig = {
  queries: {
    label: 'Queries',
    color: 'hsl(var(--primary))',
  },
}

export const syncChartConfig = {
  documents: {
    label: 'Documents',
    color: 'hsl(var(--primary))',
  },
}
