'use client'

import { Shell } from '@/components/shell'
import { Button } from '@/components/ui/button'
import { CodeBlock } from '@/components/ui/code-block'
import { CurlCommandBlock } from '@/components/ui/curl-command-block'
import { Field, FieldContent, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { IconHelpCircle } from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'

export const Route = createFileRoute('/collections/new')({
  component: NewCollectionPage,
})

function NewCollectionPage() {
  const [collectionName, setCollectionName] = React.useState('')
  const randomId = React.useRef(Math.random().toString(36).substring(2, 15))

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // TODO: Add API call to create collection
    console.log('Creating collection:', collectionName)
    // TODO: Navigate to collection page or show success message
  }

  const collectionData = React.useMemo(
    () => ({
      name: collectionName,
      id:
        collectionName
          ?.toLowerCase()
          .replace(/ /g, '-')
          .replace(/[^a-z0-9-]/g, '')
          .substring(0, 10) || 'your-collection',
      randomId: randomId.current,
    }),
    [collectionName],
  )

  const codeContent = (
    <div className="grid grid-cols-2 gap-8 p-4">
      {/* cURL Command */}
      <div className="space-y-2">
        <CurlCommandBlock
          collectionName={collectionName}
          onCollectionNameChange={setCollectionName}
          readableId={`${collectionData.id}-${collectionData.randomId}`}
        />
      </div>

      {/* Collection Preview */}
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
  )

  return (
    <Shell code={codeContent}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold mb-2">
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
                  <div className="aspect-square p-4 bg-white/70 dark:bg-zinc-800/70">
                    <div className="w-full h-full flex flex-col items-center justify-center">
                      <div className="w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center border-zinc-350 dark:border-zinc-600">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="lucide lucide-plus w-8 h-8 opacity-35 text-zinc-350 dark:text-zinc-500"
                        >
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                      </div>
                      <div className="text-[10px] font-mono opacity-35 mt-2 text-zinc-400 dark:text-zinc-500">
                        future source
                      </div>
                    </div>
                  </div>
                  <div className="aspect-square p-4 bg-white/70 dark:bg-zinc-800/70">
                    <div className="w-full h-full flex flex-col items-center justify-center">
                      <div className="w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center border-zinc-350 dark:border-zinc-600">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="lucide lucide-plus w-8 h-8 opacity-35 text-zinc-350 dark:text-zinc-500"
                        >
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                      </div>
                      <div className="text-[10px] font-mono opacity-35 mt-2 text-zinc-400 dark:text-zinc-500">
                        future source
                      </div>
                    </div>
                  </div>
                  <div className="aspect-square p-4 bg-white/70 dark:bg-zinc-800/70">
                    <div className="w-full h-full flex flex-col items-center justify-center">
                      <div className="w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center border-zinc-350 dark:border-zinc-600">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="lucide lucide-plus w-8 h-8 opacity-35 text-zinc-350 dark:text-zinc-500"
                        >
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                      </div>
                      <div className="text-[10px] font-mono opacity-35 mt-2 text-zinc-400 dark:text-zinc-500">
                        future source
                      </div>
                    </div>
                  </div>
                  <div className="aspect-square p-4 bg-white/70 dark:bg-zinc-800/70">
                    <div className="w-full h-full flex flex-col items-center justify-center">
                      <div className="w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center border-zinc-350 dark:border-zinc-600">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="lucide lucide-plus w-8 h-8 opacity-35 text-zinc-350 dark:text-zinc-500"
                        >
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                      </div>
                      <div className="text-[10px] font-mono opacity-35 mt-2 text-zinc-400 dark:text-zinc-500">
                        future source
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <p className="text-xs text-muted-foreground my-4 text-center">
                Add more source connections any time.
              </p>
            </div>
          </div>
          <div className="mt-8 flex justify-end">
            <Button type="submit">Continue</Button>
          </div>
        </form>
      </div>
    </Shell>
  )
}
