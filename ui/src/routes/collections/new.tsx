'use client'

import { Shell } from '@/components/shell'
import { Button } from '@/components/ui/button'
import { Field, FieldContent, FieldLabel } from '@/components/ui/field'
import { FutureSourcePlaceholder } from '@/components/ui/future-source-placeholder'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useCollectionData } from '@/hooks/use-collection-data'
import { IconHelpCircle } from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'

export const Route = createFileRoute('/collections/new')({
  component: NewCollectionPage,
})

function NewCollectionPage() {
  const [collectionName, setCollectionName] = React.useState('')
  const collectionData = useCollectionData(collectionName)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // API call and navigation will be added when backend integration is ready
  }

  const codeContent = (
    <iframe
      src="https://docs.airweave.ai/api-reference/collections/create-collections-post"
      className="w-full h-full"
    />
  )

  return (
    <Shell code={codeContent}>
      <div className="w-4xl max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="font-mono text-lg uppercase">
            Create a new collection
          </h1>
          <p className="text-sm text-muted-foreground">
            Collections group your data sources for unified search
            <Tooltip>
              <TooltipTrigger className="ml-1.5">
                <IconHelpCircle className="size-3 translate-y-px" />
              </TooltipTrigger>
              <TooltipContent>
                A collection is like a folder that groups related data sources.
                It can include multiple sources from a user, organization, or
                project. When your agent searches, it queries all sources in the
                collection at once; for example, you can group all HR tools
                (e.g., Jira, Notion, Google Drive) into one searchable
                collection.
              </TooltipContent>
            </Tooltip>
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-2 gap-8">
            <div className="space-y-4">
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
              <div className="flex justify-end">
                <Button type="submit">Continue</Button>
              </div>
            </div>
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
        </form>
      </div>
    </Shell>
  )
}
