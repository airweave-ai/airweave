import { Shell } from '@/components/shell'
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
  IconPencil,
  IconPlug,
  IconPlus,
  IconSearch,
  IconTrash,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'
import { SourceAvatars } from '@/features/collections/components/source-avatars'
import { StatusBadge } from '@/features/collections/components/status-badge'
import { collections } from '@/features/collections/data/mock-collections'

export const Route = createFileRoute('/collections/')({
  component: CollectionsPage,
})

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
