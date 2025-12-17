import { Shell } from '@/components/shell'
import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  IconAdjustments,
  IconAlertCircle,
  IconCircleDot,
  IconClock,
  IconDatabase,
  IconFilter,
  IconKey,
  IconLoader2,
  IconPlug,
  IconPlus,
  IconSearch,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'

export const Route = createFileRoute('/source-connections')({
  component: SourceConnectionsPage,
})

interface SourceConnection {
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

const sourceConnections: SourceConnection[] = [
  {
    id: '1',
    account: 'anand@airweave.ai',
    shortName: 'gmail',
    collectionId: 'anands-collection-4m6pbv',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 1247,
    federatedSearch: false,
    createdAt: '2 days ago',
    modifiedAt: '5 min ago',
  },
  {
    id: '2',
    account: 'U04MDQX8R7P',
    shortName: 'slack',
    collectionId: 'marketing-assets-8k2nxp',
    status: 'syncing',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 892,
    federatedSearch: false,
    createdAt: '1 week ago',
    modifiedAt: '2 min ago',
  },
  {
    id: '3',
    account: 'anand@company.notion.so',
    shortName: 'notion',
    collectionId: 'engineering-docs-3j9mvz',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 3421,
    federatedSearch: true,
    createdAt: '2 weeks ago',
    modifiedAt: '1 hour ago',
  },
  {
    id: '4',
    account: 'AnandChowdhary',
    shortName: 'github',
    collectionId: 'engineering-docs-3j9mvz',
    status: 'pending_auth',
    authMethod: 'oauth_browser',
    isAuthenticated: false,
    entityCount: 0,
    federatedSearch: false,
    createdAt: '1 day ago',
    modifiedAt: '1 day ago',
  },
  {
    id: '5',
    account: '0053h000002xQ1YAAU',
    shortName: 'salesforce',
    collectionId: 'sales-pipeline-2m8fht',
    status: 'error',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 2103,
    federatedSearch: false,
    createdAt: '1 month ago',
    modifiedAt: '3 hours ago',
  },
  {
    id: '6',
    account: 'anand@airweave.atlassian.net',
    shortName: 'atlassian',
    collectionId: 'product-roadmap-9n3wqx',
    status: 'inactive',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 456,
    federatedSearch: false,
    createdAt: '2 months ago',
    modifiedAt: '2 weeks ago',
  },
  {
    id: '7',
    account: 'anand@airweave.ai',
    shortName: 'google',
    collectionId: 'hr-resources-5k7pmt',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 1834,
    federatedSearch: true,
    createdAt: '3 months ago',
    modifiedAt: '30 min ago',
  },
  {
    id: '8',
    account: 'acct_1NqX2kLkdIwHu7ix',
    shortName: 'stripe',
    collectionId: 'financial-records-1h6cvn',
    status: 'pending_sync',
    authMethod: 'direct',
    isAuthenticated: true,
    entityCount: 0,
    federatedSearch: false,
    createdAt: '1 hour ago',
    modifiedAt: '1 hour ago',
  },
  {
    id: '9',
    account: 'postgres@db.airweave.ai',
    shortName: 'postgresql',
    collectionId: 'research-data-4w2jbp',
    status: 'active',
    authMethod: 'direct',
    isAuthenticated: true,
    entityCount: 12456,
    federatedSearch: false,
    createdAt: '3 months ago',
    modifiedAt: '15 min ago',
  },
  {
    id: '10',
    account: '1204823456789012',
    shortName: 'asana',
    collectionId: 'client-projects-8m5rzq',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 3287,
    federatedSearch: false,
    createdAt: '3 months ago',
    modifiedAt: '45 min ago',
  },
  {
    id: '11',
    account: 'sales@airweave.ai',
    shortName: 'hubspot',
    collectionId: 'customer-success-9k2lxy',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 2789,
    federatedSearch: true,
    createdAt: '4 days ago',
    modifiedAt: '20 min ago',
  },
  {
    id: '12',
    account: 'support@airweave.ai',
    shortName: 'zendesk',
    collectionId: 'support-tickets-2b4cfd',
    status: 'error',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 1543,
    federatedSearch: false,
    createdAt: '1 week ago',
    modifiedAt: '10 min ago',
  },
  {
    id: '13',
    account: 'files@airweave.ai',
    shortName: 'dropbox',
    collectionId: 'design-assets-7m2kxr',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 987,
    federatedSearch: false,
    createdAt: '2 weeks ago',
    modifiedAt: '3 hours ago',
  },
  {
    id: '14',
    account: 'legal@airweave.ai',
    shortName: 'box',
    collectionId: 'contracts-1k9bqt',
    status: 'inactive',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 312,
    federatedSearch: false,
    createdAt: '1 month ago',
    modifiedAt: '1 week ago',
  },
  {
    id: '15',
    account: 'm365@airweave.ai',
    shortName: 'microsoft',
    collectionId: 'sharepoint-sites-5t8pvr',
    status: 'pending_sync',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 0,
    federatedSearch: true,
    createdAt: '3 days ago',
    modifiedAt: '3 days ago',
  },
  {
    id: '16',
    account: 'ops@airweave.ai',
    shortName: 'airtable',
    collectionId: 'ops-tracking-6y1nqd',
    status: 'syncing',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 1456,
    federatedSearch: false,
    createdAt: '5 days ago',
    modifiedAt: '1 min ago',
  },
  {
    id: '17',
    account: 'bugs@airweave.ai',
    shortName: 'linear',
    collectionId: 'issue-tracker-1r6fzp',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 2154,
    federatedSearch: false,
    createdAt: '2 months ago',
    modifiedAt: '12 min ago',
  },
  {
    id: '18',
    account: 'datasync@airweave.ai',
    shortName: 'postgresql',
    collectionId: 'analytics-warehouse-3g7tmd',
    status: 'pending_auth',
    authMethod: 'direct',
    isAuthenticated: false,
    entityCount: 0,
    federatedSearch: false,
    createdAt: '30 min ago',
    modifiedAt: '30 min ago',
  },
  {
    id: '19',
    account: 'anand@airweave.ai',
    shortName: 'gmail',
    collectionId: 'lead-intel-7b3kpv',
    status: 'active',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 1678,
    federatedSearch: false,
    createdAt: '6 months ago',
    modifiedAt: '5 min ago',
  },
  {
    id: '20',
    account: 'engineering@airweave.ai',
    shortName: 'github',
    collectionId: 'platform-repos-2f9cjh',
    status: 'syncing',
    authMethod: 'oauth_browser',
    isAuthenticated: true,
    entityCount: 4321,
    federatedSearch: true,
    createdAt: '4 months ago',
    modifiedAt: 'just now',
  },
]

const collectionNameMap: Record<string, string> = {
  'anands-collection-4m6pbv': "Anand's collection",
  'marketing-assets-8k2nxp': 'Marketing assets',
  'engineering-docs-3j9mvz': 'Engineering docs',
  'sales-pipeline-2m8fht': 'Sales pipeline',
  'product-roadmap-9n3wqx': 'Product roadmap',
  'hr-resources-5k7pmt': 'HR resources',
  'financial-records-1h6cvn': 'Financial records',
  'research-data-4w2jbp': 'Research data',
  'client-projects-8m5rzq': 'Client projects',
  'customer-success-9k2lxy': 'Customer success',
  'support-tickets-2b4cfd': 'Support tickets',
  'design-assets-7m2kxr': 'Design assets',
  'contracts-1k9bqt': 'Contracts',
  'sharepoint-sites-5t8pvr': 'SharePoint sites',
  'ops-tracking-6y1nqd': 'Ops tracking',
  'issue-tracker-1r6fzp': 'Issue tracker',
  'analytics-warehouse-3g7tmd': 'Analytics warehouse',
  'lead-intel-7b3kpv': 'Lead intelligence',
  'platform-repos-2f9cjh': 'Platform repos',
}

function getCollectionName(id: string) {
  return collectionNameMap[id] ?? id
}

const sourceSlugMap: Record<string, string> = {
  gmail: 'google',
  slack: 'slackhq',
  notion: 'makenotion',
  github: 'github',
  salesforce: 'salesforce',
  atlassian: 'atlassian',
  google: 'google',
  stripe: 'stripe',
  postgresql: 'postgresql',
  asana: 'asana',
  hubspot: 'hubspot',
  zendesk: 'zendesk',
  dropbox: 'dropbox',
  box: 'box',
  microsoft: 'microsoft',
  airtable: 'airtable',
  linear: 'linear',
}

function StatusBadge({ status }: { status: SourceConnection['status'] }) {
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
    pending_auth: {
      indicator: <IconKey className="size-3" />,
      badge:
        'bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-400',
      label: 'Pending Auth',
    },
    pending_sync: {
      indicator: <IconClock className="size-3" />,
      badge:
        'bg-gray-50 border-gray-200 text-gray-600 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400',
      label: 'Pending Sync',
    },
    error: {
      indicator: <IconAlertCircle className="size-3" />,
      badge:
        'bg-red-50 border-red-200 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-400',
      label: 'Error',
    },
    inactive: {
      indicator: <span className="size-1.5 rounded-full bg-gray-400" />,
      badge:
        'bg-gray-50 border-gray-200 text-gray-600 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400',
      label: 'Inactive',
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

function AuthMethodBadge({
  method,
}: {
  method: SourceConnection['authMethod']
}) {
  const methodConfig: Record<
    SourceConnection['authMethod'],
    { label: string; className: string }
  > = {
    oauth_browser: {
      label: 'OAuth',
      className:
        'bg-violet-50 border-violet-200 text-violet-700 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-400',
    },
    oauth_token: {
      label: 'OAuth Token',
      className:
        'bg-violet-50 border-violet-200 text-violet-700 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-400',
    },
    oauth_byoc: {
      label: 'OAuth BYOC',
      className:
        'bg-violet-50 border-violet-200 text-violet-700 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-400',
    },
    direct: {
      label: 'Direct',
      className:
        'bg-slate-50 border-slate-200 text-slate-700 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-400',
    },
    auth_provider: {
      label: 'Auth Provider',
      className:
        'bg-indigo-50 border-indigo-200 text-indigo-700 dark:bg-indigo-950 dark:border-indigo-800 dark:text-indigo-400',
    },
  }

  const config = methodConfig[method]

  return <Badge className={config.className}>{config.label}</Badge>
}

function SourceAvatar({ shortName }: { shortName: string }) {
  return (
    <div className="flex items-center gap-2">
      <Avatar size="sm">
        <AvatarImage
          src={`https://github.com/${sourceSlugMap[shortName] || shortName}.png`}
          alt={shortName}
        />
      </Avatar>
      <span className="capitalize">{shortName}</span>
    </div>
  )
}

function SourceConnectionsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const filteredConnections = useMemo(() => {
    if (!searchQuery.trim()) return sourceConnections

    const query = searchQuery.toLowerCase()
    return sourceConnections.filter(
      (connection) =>
        connection.account.toLowerCase().includes(query) ||
        connection.shortName.toLowerCase().includes(query) ||
        connection.status.toLowerCase().includes(query),
    )
  }, [searchQuery])

  return (
    <Shell
      askTitle="source connections"
      askDescription="Source connections are authenticated links to your data sources like Gmail, Slack, or Notion."
      askSuggestions={[
        'How do I connect a new source?',
        'Why is my connection pending auth?',
        'How do I re-authenticate?',
        'What does federated search mean?',
      ]}
    >
      <header className="flex items-center gap-8 border-b border-muted px-6 py-3">
        <h1 className="font-mono uppercase text-sm font-semibold">
          Source Connections
        </h1>
        <section className="flex items-center gap-2">
          <Button variant="outline" size="icon-xs">
            <IconSearch className="size-3" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="outline" size="xs">
                  <IconFilter className="size-3" />
                  Filter
                </Button>
              }
            />
            <DropdownMenuContent className="w-44">
              <DropdownMenuItem>
                <IconCircleDot className="size-4 opacity-60" />
                Status
              </DropdownMenuItem>
              <DropdownMenuItem>
                <IconPlug className="size-4 opacity-60" />
                Source
              </DropdownMenuItem>
              <DropdownMenuItem>
                <IconKey className="size-4 opacity-60" />
                Auth Method
              </DropdownMenuItem>
              <DropdownMenuItem>
                <IconDatabase className="size-4 opacity-60" />
                Entities
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="outline" size="icon-xs">
            <IconAdjustments className="size-3" />
          </Button>
        </section>
        <div className="ml-auto flex items-center gap-4">
          <input
            ref={inputRef}
            placeholder="Press / to search"
            className="h-8 w-56 rounded-md border border-border bg-background px-3 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <span className="text-sm text-muted-foreground">
            {filteredConnections.length} of {sourceConnections.length}{' '}
            {sourceConnections.length === 1 ? 'connection' : 'connections'}
          </span>
          <Button size="sm">
            <IconPlus className="size-3" />
            Connect new source
          </Button>
        </div>
      </header>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="pl-6">Status</TableHead>
            <TableHead>Account</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Collection</TableHead>
            <TableHead>Auth Method</TableHead>
            <TableHead>Entities</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right pr-6">Last Synced</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredConnections.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={8}
                className="h-24 text-center text-muted-foreground"
              >
                No connections found matching "{searchQuery}"
              </TableCell>
            </TableRow>
          ) : (
            filteredConnections.map((connection) => (
              <TableRow key={connection.id}>
                <TableCell className="pl-6">
                  <StatusBadge status={connection.status} />
                </TableCell>
                <TableCell className="font-mono text-sm text-muted-foreground">
                  {connection.account}
                </TableCell>
                <TableCell>
                  <SourceAvatar shortName={connection.shortName} />
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <div className="space-y-1">
                    <span className="font-medium text-foreground">
                      {getCollectionName(connection.collectionId)}
                    </span>
                    {/* <div className="font-mono text-xs opacity-70">
                      {connection.collectionId}
                    </div> */}
                  </div>
                </TableCell>
                <TableCell>
                  <AuthMethodBadge method={connection.authMethod} />
                </TableCell>
                <TableCell className="text-muted-foreground tabular-nums">
                  {connection.entityCount.toLocaleString()}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {connection.createdAt}
                </TableCell>
                <TableCell className="text-right text-muted-foreground pr-6">
                  {connection.modifiedAt}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </Shell>
  )
}
