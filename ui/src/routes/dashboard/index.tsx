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
  IconArrowRight,
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
import { MetricCard } from '@/features/dashboard/components/metric-card'
import { StatusBadge } from '@/features/dashboard/components/status-badge'
import {
  mockDataByTimeRange,
  needsAttention,
  queryChartConfig,
  recentConnections,
  syncChartConfig,
  timeRangeLabels,
  topCollections,
} from '@/features/dashboard/data/mock-data'
import type { TimeRange } from '@/features/dashboard/data/types'

export const Route = createFileRoute('/dashboard/')({
  component: DashboardPage,
})

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
