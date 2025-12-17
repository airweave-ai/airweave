import { Shell } from '@/components/shell'
import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  IconAlertCircle,
  IconArrowDownRight,
  IconArrowRight,
  IconArrowUpRight,
  IconChevronDown,
  IconClock,
  IconKey,
  IconLoader2,
  IconRefresh,
  IconSearch,
  IconTrendingUp,
} from '@tabler/icons-react'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from 'recharts'

export const Route = createFileRoute('/dashboard')({
  component: DashboardPage,
})

// Time range options
type TimeRange = 'last_hour' | 'last_24h' | 'last_7d' | 'last_30d'

const timeRangeLabels: Record<TimeRange, string> = {
  last_hour: 'Last hour',
  last_24h: 'Last 24 hours',
  last_7d: 'Last 7 days',
  last_30d: 'Last 30 days',
}

// Mock data for different time ranges
const mockDataByTimeRange: Record<
  TimeRange,
  {
    metrics: {
      queries: { value: number; change: number; trend: 'up' | 'down' }
      documentsSynced: { value: number; collections: number }
      activeSyncs: { value: number; completingSoon: number }
      errors: { value: number; needsAttention: boolean }
    }
    queryVolumeChart: Array<{ time: string; queries: number }>
    syncActivityChart: Array<{
      time: string
      documents: number
      sources: number
    }>
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

// Needs attention data (always current)
const needsAttention = {
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

// Top collections mock data
const topCollections = [
  {
    id: '1',
    name: "Anand's collection",
    queries: 1247,
    entities: 3421,
    status: 'active' as const,
  },
  {
    id: '2',
    name: 'Engineering Docs',
    queries: 892,
    entities: 5672,
    status: 'syncing' as const,
  },
  {
    id: '3',
    name: 'Customer Support',
    queries: 654,
    entities: 2103,
    status: 'active' as const,
  },
  {
    id: '4',
    name: 'Marketing Assets',
    queries: 421,
    entities: 1834,
    status: 'active' as const,
  },
  {
    id: '5',
    name: 'Sales Pipeline',
    queries: 312,
    entities: 892,
    status: 'active' as const,
  },
]

// Recent connections mock data
const recentConnections = [
  {
    id: '1',
    source: 'github',
    sourceName: 'GitHub',
    account: 'airweave-ai',
    status: 'active' as const,
    lastSynced: '2 min ago',
  },
  {
    id: '2',
    source: 'makenotion',
    sourceName: 'Notion',
    account: 'workspace',
    status: 'syncing' as const,
    lastSynced: '5 min ago',
  },
  {
    id: '3',
    source: 'slackhq',
    sourceName: 'Slack',
    account: 'airweave',
    status: 'error' as const,
    lastSynced: '1 hour ago',
  },
  {
    id: '4',
    source: 'linear',
    sourceName: 'Linear',
    account: 'airweave',
    status: 'active' as const,
    lastSynced: '15 min ago',
  },
  {
    id: '5',
    source: 'google',
    sourceName: 'Google Drive',
    account: 'team@airweave.ai',
    status: 'active' as const,
    lastSynced: '30 min ago',
  },
]

// Chart configs
const queryChartConfig = {
  queries: {
    label: 'Queries',
    color: 'hsl(var(--primary))',
  },
}

const syncChartConfig = {
  documents: {
    label: 'Documents',
    color: 'hsl(var(--primary))',
  },
}

function MetricCard({
  title,
  value,
  subtitle,
  change,
  trend,
  icon,
  isError,
}: {
  title: string
  value: string | number
  subtitle: string
  change?: number
  trend?: 'up' | 'down'
  icon: React.ReactNode
  isError?: boolean
}) {
  return (
    <Card className={isError ? 'border-red-200 dark:border-red-900' : ''}>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-muted-foreground uppercase font-mono text-xs">
            <span className="text-sm font-medium">{title}</span>
          </div>
          {change !== undefined && trend && (
            <div
              className={`flex items-center gap-1 text-xs ${trend === 'up' ? 'text-emerald-600' : 'text-red-600'}`}
            >
              {trend === 'up' ? (
                <IconArrowUpRight className="size-3" />
              ) : (
                <IconArrowDownRight className="size-3" />
              )}
              {Math.abs(change)}%
            </div>
          )}
        </div>
        <div className="mt-2">
          <div
            className={`text-3xl font-lighter tabular-nums ${isError ? 'text-red-600' : ''}`}
          >
            {typeof value === 'number' ? value.toLocaleString() : value}
          </div>
          <div className="text-sm text-muted-foreground mt-1">{subtitle}</div>
        </div>
      </CardContent>
    </Card>
  )
}

function StatusBadge({
  status,
}: {
  status: 'active' | 'syncing' | 'error' | 'pending_auth'
}) {
  const statusConfig = {
    active: {
      indicator: <span className="size-1.5 rounded-full bg-emerald-500" />,
      badge:
        'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-400',
      label: 'Active',
    },
    syncing: {
      indicator: <IconLoader2 className="size-3 animate-spin" />,
      badge:
        'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-400',
      label: 'Syncing',
    },
    error: {
      indicator: <IconAlertCircle className="size-3" />,
      badge:
        'bg-red-50 border-red-200 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-400',
      label: 'Error',
    },
    pending_auth: {
      indicator: <IconKey className="size-3" />,
      badge:
        'bg-orange-50 border-orange-200 text-orange-700 dark:bg-orange-950 dark:border-orange-800 dark:text-orange-400',
      label: 'Auth Required',
    },
  }

  const config = statusConfig[status]

  return (
    <Badge className={`${config.badge} gap-1.5`}>
      {config.indicator}
      {config.label}
    </Badge>
  )
}

function DashboardPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>('last_hour')

  const data = useMemo(() => mockDataByTimeRange[timeRange], [timeRange])

  return (
    <Shell
      askTitle="dashboard"
      askDescription="Your activity dashboard showing real-time metrics, sync status, and items needing attention."
      askSuggestions={[
        'How do I fix a failed sync?',
        'What does pending auth mean?',
        'How can I improve query performance?',
        'How do I add a new source?',
      ]}
    >
      {/* Header */}
      <header className="flex items-center justify-between border-b border-muted px-6 py-3">
        <h1 className="font-mono uppercase text-sm font-semibold">Dashboard</h1>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="outline" size="sm">
                <IconClock className="size-3.5" />
                {timeRangeLabels[timeRange]}
                <IconChevronDown className="size-3.5" />
              </Button>
            }
          />
          <DropdownMenuContent align="end">
            {(Object.entries(timeRangeLabels) as [TimeRange, string][]).map(
              ([key, label]) => (
                <DropdownMenuItem key={key} onClick={() => setTimeRange(key)}>
                  {label}
                </DropdownMenuItem>
              ),
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <div className="p-6 space-y-6">
        {/* Metric Cards */}
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard
            title="Queries"
            value={data.metrics.queries.value}
            subtitle={`${data.metrics.queries.trend === 'up' ? '+' : ''}${data.metrics.queries.change}% from previous period`}
            change={data.metrics.queries.change}
            trend={data.metrics.queries.trend}
            icon={<IconSearch className="size-4" />}
          />
          <MetricCard
            title="Documents Synced"
            value={data.metrics.documentsSynced.value}
            subtitle={`across ${data.metrics.documentsSynced.collections} collections`}
            icon={<IconTrendingUp className="size-4" />}
          />
          <MetricCard
            title="Active Syncs"
            value={data.metrics.activeSyncs.value}
            subtitle={
              data.metrics.activeSyncs.completingSoon > 0
                ? `${data.metrics.activeSyncs.completingSoon} completing soon`
                : 'All syncs idle'
            }
            icon={<IconLoader2 className="size-4" />}
          />
          <MetricCard
            title="Errors"
            value={data.metrics.errors.value}
            subtitle={
              data.metrics.errors.needsAttention
                ? 'Needs attention'
                : 'All clear'
            }
            icon={<IconAlertCircle className="size-4" />}
            isError={data.metrics.errors.needsAttention}
          />
        </section>

        {/* Charts */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Query Volume
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer
                config={queryChartConfig}
                className="h-[200px] w-full"
              >
                <AreaChart
                  data={data.queryVolumeChart}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="queryGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="time"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => value.toLocaleString()}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Area
                    type="monotone"
                    dataKey="queries"
                    stroke="hsl(var(--primary))"
                    fill="url(#queryGradient)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ChartContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Sync Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer
                config={syncChartConfig}
                className="h-[200px] w-full"
              >
                <BarChart
                  data={data.syncActivityChart}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="time"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => value.toLocaleString()}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar
                    dataKey="documents"
                    fill="hsl(var(--primary))"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartContainer>
            </CardContent>
          </Card>
        </section>

        {/* Needs Attention */}
        {(needsAttention.failedSyncs.length > 0 ||
          needsAttention.pendingAuth.length > 0) && (
          <section>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <IconAlertCircle className="size-4 text-red-500" />
              Needs Attention
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {needsAttention.failedSyncs.map((item) => (
                <Card
                  key={item.id}
                  className="border-red-200 dark:border-red-900"
                >
                  <CardContent>
                    <div className="flex items-start gap-3">
                      <Avatar size="sm">
                        <AvatarImage
                          src={`https://github.com/${item.source}.png`}
                          alt={item.sourceName}
                        />
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">
                            {item.sourceName}
                          </span>
                          <Badge variant="destructive" className="text-xs">
                            Failed
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {item.collection}
                        </div>
                        <div className="text-xs text-red-600 dark:text-red-400 mt-1">
                          {item.error}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {item.time}
                        </div>
                      </div>
                      <Button size="sm" variant="outline">
                        <IconRefresh className="size-3" />
                        Retry
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {needsAttention.pendingAuth.map((item) => (
                <Card
                  key={item.id}
                  className="border-orange-200 dark:border-orange-900"
                >
                  <CardContent>
                    <div className="flex items-start gap-3">
                      <Avatar size="sm">
                        <AvatarImage
                          src={`https://github.com/${item.source}.png`}
                          alt={item.sourceName}
                        />
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">
                            {item.sourceName}
                          </span>
                          <Badge className="text-xs bg-orange-50 border-orange-200 text-orange-700 dark:bg-orange-950 dark:border-orange-800 dark:text-orange-400">
                            <IconKey className="size-2.5" />
                            Auth Required
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {item.collection}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {item.account}
                        </div>
                      </div>
                      <Button size="sm" variant="outline">
                        <IconKey className="size-3" />
                        Connect
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Tables */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Top Collections */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  Top Collections
                </CardTitle>
                <Link to="/collections">
                  <Button variant="ghost" size="sm" className="text-xs">
                    View all
                    <IconArrowRight className="size-3" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-4">Name</TableHead>
                    <TableHead className="text-right">Queries</TableHead>
                    <TableHead className="text-right">Entities</TableHead>
                    <TableHead className="pr-4">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {topCollections.map((collection) => (
                    <TableRow key={collection.id}>
                      <TableCell className="pl-4 font-medium">
                        {collection.name}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {collection.queries.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {collection.entities.toLocaleString()}
                      </TableCell>
                      <TableCell className="pr-4">
                        <StatusBadge status={collection.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Recent Source Connections */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  Recent Source Connections
                </CardTitle>
                <Link to="/source-connections">
                  <Button variant="ghost" size="sm" className="text-xs">
                    View all
                    <IconArrowRight className="size-3" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-4">Source</TableHead>
                    <TableHead>Account</TableHead>
                    <TableHead>Last Synced</TableHead>
                    <TableHead className="pr-4">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentConnections.map((connection) => (
                    <TableRow key={connection.id}>
                      <TableCell className="pl-4">
                        <div className="flex items-center gap-2">
                          <Avatar size="sm">
                            <AvatarImage
                              src={`https://github.com/${connection.source}.png`}
                              alt={connection.sourceName}
                            />
                          </Avatar>
                          <span className="font-medium">
                            {connection.sourceName}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {connection.account}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {connection.lastSynced}
                      </TableCell>
                      <TableCell className="pr-4">
                        <StatusBadge status={connection.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </section>
      </div>
    </Shell>
  )
}
