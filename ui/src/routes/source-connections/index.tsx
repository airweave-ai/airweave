import { Shell } from '@/components/shell'
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
  IconCircleDot,
  IconDatabase,
  IconFilter,
  IconKey,
  IconPlug,
  IconPlus,
  IconSearch,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AuthMethodBadge } from '@/features/source-connections/components/auth-method-badge'
import { SourceAvatar } from '@/features/source-connections/components/source-avatar'
import { StatusBadge } from '@/features/source-connections/components/status-badge'
import { getCollectionName, sourceConnections } from '@/features/source-connections/data/mock-connections'

export const Route = createFileRoute('/source-connections/')({
  component: SourceConnectionsPage,
})

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
                  <span className="font-medium text-foreground">
                    {getCollectionName(connection.collectionId)}
                  </span>
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
