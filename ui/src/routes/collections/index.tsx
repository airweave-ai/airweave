import { Shell } from '@/components/shell'
import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
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
  IconCircleDot,
  IconClock,
  IconCopy,
  IconDatabase,
  IconDots,
  IconFileDownload,
  IconFilter,
  IconLoader2,
  IconPencil,
  IconPlug,
  IconPlus,
  IconSearch,
  IconTrash,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'

export const Route = createFileRoute('/collections/')({
  component: CollectionsPage,
})

interface Collection {
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

const collections: Collection[] = [
  {
    id: '1',
    name: "Anand's collection",
    domain: 'anands-collection-4m6pbv',
    status: 'active',
    sources: ['makenotion', 'asana', 'linear'],
    lastSynced: '2 min ago',
    createdAt: '2 min ago',
    entities: 1247,
    size: 4531,
  },
  {
    id: '2',
    name: 'Marketing Assets',
    domain: 'marketing-assets-8k2nxp',
    status: 'active',
    sources: ['google', 'dropbox'],
    lastSynced: '5 min ago',
    createdAt: '2 days ago',
    entities: 892,
    size: 65432,
  },
  {
    id: '3',
    name: 'Engineering Docs',
    domain: 'engineering-docs-3j9mvz',
    status: 'syncing',
    sources: ['github', 'atlassian', 'makenotion'],
    lastSynced: '1 hour ago',
    createdAt: '1 day ago',
    entities: 3421,
    size: 216,
  },
  {
    id: '4',
    name: 'Customer Support',
    domain: 'customer-support-7r4kls',
    status: 'active',
    sources: ['zendesk', 'slackhq'],
    lastSynced: '10 min ago',
    entities: 5672,
    createdAt: '1 week ago',
    size: 92487,
  },
  {
    id: '5',
    name: 'Sales Pipeline',
    domain: 'sales-pipeline-2m8fht',
    status: 'active',
    sources: ['hubspot', 'salesforce'],
    lastSynced: '15 min ago',
    entities: 2103,
    createdAt: '1 month ago',
    size: 1024,
  },
  {
    id: '6',
    name: 'Product Roadmap',
    domain: 'product-roadmap-9n3wqx',
    status: 'paused',
    sources: ['linear', 'atlassian'],
    lastSynced: '2 days ago',
    entities: 456,
    createdAt: '2 months ago',
    size: 3121,
  },
  {
    id: '7',
    name: 'HR Resources',
    domain: 'hr-resources-5k7pmt',
    status: 'active',
    sources: ['google', 'microsoft'],
    lastSynced: '30 min ago',
    entities: 1834,
    createdAt: '3 months ago',
    size: 5432,
  },
  {
    id: '8',
    name: 'Financial Records',
    domain: 'financial-records-1h6cvn',
    status: 'active',
    sources: ['stripe', 'airtable'],
    lastSynced: '1 hour ago',
    entities: 7891,
    createdAt: '3 months ago',
    size: 1024,
  },
  {
    id: '9',
    name: 'Research Data',
    domain: 'research-data-4w2jbp',
    status: 'syncing',
    sources: ['postgresql', 'google'],
    lastSynced: '3 hours ago',
    entities: 12456,
    createdAt: '3 months ago',
    size: 345231,
  },
  {
    id: '10',
    name: 'Client Projects',
    domain: 'client-projects-8m5rzq',
    status: 'active',
    sources: ['asana', 'box', 'slackhq'],
    lastSynced: '45 min ago',
    entities: 3287,
    createdAt: '3 months ago',
    size: 345231,
  },
]

const sourceSlugMap: Record<string, string> = {
  notion: 'makenotion',
  makenotion: 'makenotion',
  asana: 'asana',
  linear: 'linear',
  google: 'google',
  dropbox: 'dropbox',
  github: 'github',
  atlassian: 'atlassian',
  zendesk: 'zendesk',
  slackhq: 'slackhq',
  hubspot: 'hubspot',
  salesforce: 'salesforce',
  microsoft: 'microsoft',
  stripe: 'stripe',
  airtable: 'airtable',
  postgresql: 'postgresql',
  box: 'box',
}

function StatusBadge({ status }: { status: Collection['status'] }) {
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
    paused: {
      indicator: <span className="size-1.5 rounded-full bg-gray-400" />,
      badge:
        'bg-gray-50 border-gray-200 text-gray-600 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400',
      label: 'Paused',
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

function SourceAvatars({ sources }: { sources: string[] }) {
  return (
    <div className="flex -space-x-1.5 *:ring-2 *:ring-background">
      {sources.slice(0, 4).map((source) => (
        <Avatar key={source} size="sm">
          <AvatarImage
            src={`https://github.com/${sourceSlugMap[source] || source}.png`}
            alt={source}
          />
        </Avatar>
      ))}
      {sources.length > 4 && (
        <div className="flex items-center justify-center size-6 rounded-full bg-muted text-[10px] font-medium text-muted-foreground ring-2 ring-background">
          +{sources.length - 4}
        </div>
      )}
    </div>
  )
}

function CollectionsPage() {
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

  const filteredCollections = useMemo(() => {
    if (!searchQuery.trim()) return collections

    const query = searchQuery.toLowerCase()
    return collections.filter(
      (collection) =>
        collection.name.toLowerCase().includes(query) ||
        collection.domain.toLowerCase().includes(query) ||
        collection.status.toLowerCase().includes(query),
    )
  }, [searchQuery])

  return (
    <Shell
      askTitle="collections"
      askDescription="Collections are searchable knowledge bases that combine data from your connected sources."
      askSuggestions={[
        'How do I create a collection?',
        'How do I connect sources?',
        'How does search work?',
        'How do I pause or resume a sync?',
      ]}
    >
      <header className="flex items-center gap-8 border-b border-muted px-6 py-3">
        <h1 className="font-mono uppercase text-sm font-semibold">
          Collections
        </h1>
        <section className="flex items-center gap-2">
          <Button variant="outline" size="icon-xs">
            <IconSearch className="size-3" />
          </Button>
          {/* <InputGroup className="w-36">
          <InputGroupAddon>
            <IconSearch className="size-4" />
          </InputGroupAddon>
          <InputGroupInput
            ref={inputRef}
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </InputGroup> */}
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
                <IconClock className="size-4 opacity-60" />
                Last Synced
              </DropdownMenuItem>
              <DropdownMenuItem>
                <IconFileDownload className="size-4 opacity-60" />
                Vector Size
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
          <span className="text-sm text-muted-foreground">
            {filteredCollections.length} of {collections.length}{' '}
            {collections.length === 1 ? 'collection' : 'collections'}
          </span>
          <Button size="sm">
            <IconPlus className="size-3" />
            New collection
          </Button>
        </div>
      </header>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="pl-12">Status</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Domain</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Last Synced</TableHead>
            <TableHead>Vector Size</TableHead>
            <TableHead className="text-right pr-14">Entities</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredCollections.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={6}
                className="h-24 text-center text-muted-foreground"
              >
                No collections found matching "{searchQuery}"
              </TableCell>
            </TableRow>
          ) : (
            filteredCollections.map((collection) => (
              <TableRow key={collection.id}>
                <TableCell className="pl-3 flex items-center gap-4">
                  <div>
                    <Checkbox />
                  </div>
                  <div>
                    <StatusBadge status={collection.status} />
                  </div>
                </TableCell>
                <TableCell className="font-medium">{collection.name}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {collection.domain}.airweave.ai
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {collection.createdAt}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {collection.lastSynced}
                </TableCell>
                <TableCell className="text-muted-foreground tabular-nums">
                  {collection.size.toLocaleString()}
                </TableCell>
                <TableCell className="text-right tabular-nums flex items-center gap-6 justify-end">
                  <SourceAvatars sources={collection.sources} />
                  <div className="w-12">
                    {collection.entities.toLocaleString()}
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger>
                      <Button variant="ghost" size="icon-xs">
                        <IconDots className="size-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem>
                        <IconPencil className="size-4 opacity-60" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger>
                          <IconCopy className="size-4 opacity-60" />
                          Copy
                        </DropdownMenuSubTrigger>
                        <DropdownMenuPortal>
                          <DropdownMenuSubContent>
                            <DropdownMenuItem
                              onClick={() => {
                                navigator.clipboard.writeText(collection.id)
                              }}
                            >
                              Copy ID
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                navigator.clipboard.writeText(
                                  JSON.stringify({ id: collection.id }),
                                )
                              }}
                            >
                              Copy as JSON
                            </DropdownMenuItem>
                          </DropdownMenuSubContent>
                        </DropdownMenuPortal>
                      </DropdownMenuSub>
                      <DropdownMenuItem>
                        <IconTrash className="size-4 opacity-60" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </Shell>
  )
}
