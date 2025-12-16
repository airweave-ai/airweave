'use client'

import { Button } from '@/components/ui/button'
import { CodeBlock } from '@/components/ui/code-block'
import { CurlCommandBlock } from '@/components/ui/curl-command-block'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldContent, FieldLabel } from '@/components/ui/field'
import { FutureSourcePlaceholder } from '@/components/ui/future-source-placeholder'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useCollectionData } from '@/hooks/use-collection-data'
import { IconCode, IconHelpCircle, IconPencil } from '@tabler/icons-react'
import * as React from 'react'

interface CreateCollectionProps {
  open: boolean
  onOpenChange: React.Dispatch<React.SetStateAction<boolean>>
}

export function CreateCollection({
  open,
  onOpenChange,
}: CreateCollectionProps) {
  const [collectionName, setCollectionName] = React.useState('')
  const collectionData = useCollectionData(collectionName)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // API call will be added when backend integration is ready
    onOpenChange(false)
    setCollectionName('')
  }

  const handleOpenChange = (newOpen: boolean) => {
    onOpenChange(newOpen)
    if (!newOpen) {
      setCollectionName('')
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl w-full">
        <form onSubmit={handleSubmit}>
          <Tabs defaultValue="form" className="w-full">
            <DialogHeader className="p-4 pb-0">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 space-y-2">
                  <DialogTitle>Create a new collection</DialogTitle>
                  <DialogDescription className="text-xs">
                    Collections group your data sources for unified search
                    <Tooltip>
                      <TooltipTrigger className="ml-1.5">
                        <IconHelpCircle className="size-3 translate-y-px" />
                      </TooltipTrigger>
                      <TooltipContent>
                        A collection is like a folder that groups related data
                        sources. It can include multiple sources from a user,
                        organization, or project. When your agent searches, it
                        queries all sources in the collection at once; for
                        example, you can group all HR tools (e.g., Jira, Notion,
                        Google Drive) into one searchable collection.
                      </TooltipContent>
                    </Tooltip>
                  </DialogDescription>
                </div>
                <TabsList className="mt-0">
                  <TabsTrigger value="form">
                    <IconPencil />
                    <span className="sr-only">Form</span>
                  </TabsTrigger>
                  <TabsTrigger value="code">
                    <IconCode />
                    <span className="sr-only">Code</span>
                  </TabsTrigger>
                </TabsList>
              </div>
            </DialogHeader>
            <TabsContent value="form" className="mt-4">
              <div className="grid grid-cols-2 gap-8 p-4">
                <Field>
                  <FieldLabel>
                    <Label htmlFor="collection-name">Name</Label>
                  </FieldLabel>
                  <FieldContent>
                    <Input
                      id="collection-name"
                      type="text"
                      placeholder="ACME's HR Applications"
                      value={collectionName}
                      onChange={(e) => setCollectionName(e.target.value)}
                      required
                      autoFocus
                    />
                  </FieldContent>
                </Field>
                <div className="w-full max-w-lg mx-auto">
                  <div className="rounded-t-xl border-2 border-b-0 border-dashed px-5 py-3 bg-zinc-50 border-zinc-300 dark:bg-zinc-900 dark:border-zinc-700">
                    <div className="text-xs font-mono mb-2 opacity-80 text-zinc-500 dark:text-zinc-400">
                      #{collectionData.id}-{collectionData.randomId}
                    </div>
                    <div className="flex gap-4">
                      <div className="text-xs font-medium cursor-default border-b border-transparent opacity-45 text-zinc-400 dark:text-zinc-500">
                        Search
                      </div>
                      <div className="text-xs font-medium cursor-default border-b opacity-65 text-zinc-500 dark:text-zinc-400 border-zinc-400 dark:border-zinc-600">
                        Source Connections
                      </div>
                    </div>
                  </div>
                  <div className="rounded-b-xl border-2 border-t border-dashed p-5 bg-zinc-50 border-zinc-300 dark:bg-zinc-900 dark:border-zinc-700">
                    <div className="grid grid-cols-2 gap-1 rounded-lg overflow-hidden bg-zinc-100/60 dark:bg-zinc-800/60">
                      <FutureSourcePlaceholder />
                      <FutureSourcePlaceholder />
                      <FutureSourcePlaceholder />
                      <FutureSourcePlaceholder />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground my-4 text-center">
                    Add more source connections any time.
                  </p>
                </div>
              </div>
            </TabsContent>
            <TabsContent value="code" className="mt-4">
              <div className="grid grid-cols-2 gap-8 p-4">
                <div className="space-y-2">
                  <CurlCommandBlock
                    collectionName={collectionName}
                    onCollectionNameChange={setCollectionName}
                    readableId={`${collectionData.id}-${collectionData.randomId}`}
                  />
                </div>
                <div className="space-y-2">
                  <CodeBlock
                    code={JSON.stringify(
                      {
                        id: 'string',
                        name: collectionName || 'string',
                        short_name: 'string',
                        readable_collection_id: `${collectionData.id}-${collectionData.randomId}`,
                        created_at: '2024-01-15T09:30:00Z',
                        modified_at: '2024-01-15T09:30:00Z',
                        is_authenticated: true,
                        auth_method: 'direct',
                        status: 'active',
                        entity_count: 0,
                        federated_search: false,
                      },
                      null,
                      2,
                    )}
                    language="json"
                    title="Response"
                  />
                </div>
              </div>
            </TabsContent>
          </Tabs>
          <DialogFooter>
            <Button type="submit">Continue</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
