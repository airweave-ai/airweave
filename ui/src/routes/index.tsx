import { CollectionsList } from '@/components/collections-list'
import { CreateCollection } from '@/components/create-collection'
import { Shell } from '@/components/shell'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { CodeBlock } from '@/components/ui/code-block'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  IconBrandNodejs,
  IconBrandOpenai,
  IconChevronDown,
  IconCopy,
  IconExternalLink,
  IconHelpCircle,
  IconMarkdown,
  IconMenu,
  IconPhone,
  IconPlayerPlay,
  IconThumbDown,
  IconThumbUp,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface ApiEndpoint {
  method: HttpMethod
  name: string
  request?: object
  response: string
  code: string
}

const methodColors: Record<HttpMethod, string> = {
  GET: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  POST: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
  PUT: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  PATCH: 'bg-orange-500/15 text-orange-600 dark:text-orange-400',
  DELETE: 'bg-rose-500/15 text-rose-600 dark:text-rose-400',
}

const endpoints: ApiEndpoint[] = [
  {
    method: 'GET',
    name: 'List Collections',
    code: `
import { AirweaveSDKClient } from "@airweave/sdk";
const client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY", frameworkName: "YOUR_FRAMEWORK_NAME", frameworkVersion: "YOUR_FRAMEWORK_VERSION" });
await client.collections.list({
    skip: 1,
    limit: 1,
    search: "search"
});
    `,
    response: '',
  },
  {
    method: 'GET',
    name: 'Get Collection',
    code: '',
    response: '',
  },
  {
    method: 'POST',
    name: 'Search Collection',
    code: '',
    response: '',
  },
  {
    method: 'POST',
    name: 'Create Collection',
    code: '',
    response: '',
  },
  {
    method: 'POST',
    name: 'Refresh Collection',
    code: '',
    response: '',
  },
  {
    method: 'DELETE',
    name: 'Delete Collection',
    code: '',
    response: '',
  },
]

function MethodBadge({ method }: { method: HttpMethod }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold font-mono uppercase tracking-wide',
        methodColors[method],
      )}
    >
      {method}
    </span>
  )
}

export const Route = createFileRoute('/')({ component: App })

function App() {
  const [createCollectionOpen, setCreateCollectionOpen] = React.useState(false)

  return (
    <>
      <Shell
        onNewCollectionClick={() => setCreateCollectionOpen(true)}
        docs={
          <div className="flex flex-col h-full">
            <header className="border-b shrink-0 px-4 py-2 flex justify-between items-center gap-3">
              <div className="shrink-0 flex gap-2">
                <Button variant="outline" size="icon">
                  <IconMenu />
                  <span className="sr-only">Menu</span>
                </Button>
              </div>
              <h2 className="font-medium grow truncate">Collection</h2>
              <div className="shrink-0 flex gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <Button variant="outline" size="icon">
                        <IconCopy />
                        <span className="sr-only">Copy</span>
                      </Button>
                    }
                  />
                  <DropdownMenuContent className="w-48">
                    <DropdownMenuItem>
                      <IconMarkdown className="opacity-60" />
                      Copy as markdown
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <IconBrandOpenai className="opacity-60" />
                      Open in ChatGPT
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button variant="outline" size="icon">
                  <IconExternalLink />
                  <span className="sr-only">Links</span>
                </Button>
              </div>
            </header>
            <article className="p-4 space-y-4 grow">
              <p>
                A <strong className="font-medium">Collection</strong> is a
                searchable knowledge base made up of synced data from one or
                more source connections. When you search a collection, queries
                run across all entities from all its connected sources.
              </p>
              <p>
                <strong className="font-medium">Key features:</strong>
              </p>
              <p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Unified search interface across multiple sources</li>
                  <li>Vector embeddings for semantic search</li>
                  <li>Real-time data synchronization</li>
                  <li>Configurable search parameters and filters</li>
                </ul>
              </p>
              <p className="border-t border-muted pt-4">
                <strong className="font-medium">Related topics:</strong>
              </p>
              <p>
                <ul className="list-disc list-inside space-y-1">
                  <li>
                    <a href="#" className="underline">
                      Source Connections
                    </a>
                  </li>
                  <li>
                    <a href="#" className="underline">
                      Collections API
                    </a>
                  </li>
                </ul>
              </p>
              <p className="border-t border-muted pt-4">
                <strong className="font-medium">Questions?</strong>
              </p>
              <p>
                If you have any questions, you can ask our assistant or set up a
                personalized demo call with us.
              </p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <IconHelpCircle />
                  <span>Ask</span>
                </Button>
                <Button variant="outline" size="sm">
                  <IconPhone />
                  <span>Demo</span>
                </Button>
              </div>
            </article>
            <footer className="border-t shrink-0 px-4 py-2 flex justify-between items-center">
              <h2 className="text-muted-foreground grow truncate">
                Were these docs helpful?
              </h2>
              <div className="shrink-0 flex gap-2">
                <Button variant="outline" size="sm">
                  <IconThumbUp />
                  <span>Yes</span>
                </Button>
                <Button variant="outline" size="sm">
                  <IconThumbDown />
                  <span>No</span>
                </Button>
              </div>
            </footer>
          </div>
        }
        code={
          <div className="flex flex-col h-full">
            <header className="border-b shrink-0 px-4 py-2 flex justify-between items-center gap-3">
              <div className="shrink-0 flex gap-2">
                <Button variant="outline" size="icon">
                  <IconMenu />
                  <span className="sr-only">Menu</span>
                </Button>
              </div>
              <h2 className="font-medium grow truncate">Collection</h2>
              <div className="shrink-0 flex gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <Button variant="outline">
                        <IconBrandNodejs />
                        <span>JavaScript</span>
                        <IconChevronDown />
                      </Button>
                    }
                  />
                  <DropdownMenuContent className="w-48">
                    <DropdownMenuItem>
                      <IconMarkdown className="opacity-60" />
                      Copy as markdown
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <IconBrandOpenai className="opacity-60" />
                      Open in ChatGPT
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </header>
            <Accordion>
              {endpoints.map((endpoint, index) => (
                <AccordionItem key={index} className="border-border/40">
                  <AccordionTrigger className="hover:no-underline group px-4">
                    <div className="flex items-center gap-2.5">
                      <MethodBadge method={endpoint.method} />
                      <span className="text-sm font-medium">
                        {endpoint.name}
                      </span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="p-4 pt-0 space-y-4">
                    <p className="text-xs text-muted-foreground">
                      List all collections that belong to your organization with
                      optional search filtering. Collections are always sorted
                      by creation date (newest first).
                    </p>
                    <CodeBlock
                      language="typescript"
                      code={endpoint.code.trim()}
                    />
                    <h2 className="font-medium uppercase text-xs text-muted-foreground font-mono mt-5 mb-1">
                      Authorization
                    </h2>
                    <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2 items-center">
                        <div>
                          <label className="text-xs text-muted-foreground font-mono">
                            X-API-Key
                          </label>
                          <p className="text-[70%] text-muted-foreground">
                            string &middot; required
                          </p>
                        </div>
                        <Select>
                          <SelectTrigger className="w-full">
                            <SelectValue className="font-mono">
                              YSh6L_*********
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="1">API Key 1</SelectItem>
                            <SelectItem value="2">API Key 2</SelectItem>
                            <SelectItem value="3">API Key 3</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <h2 className="font-medium uppercase text-xs text-muted-foreground font-mono mt-5 mb-1">
                      Query params
                    </h2>
                    <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2 items-center">
                        <div>
                          <label className="text-xs text-muted-foreground font-mono">
                            Skip
                          </label>
                          <p className="text-[70%] text-muted-foreground">
                            integer &middot; optional &middot; default: 0
                          </p>
                        </div>
                        <Input type="number" defaultValue="0" />
                      </div>
                      <div className="grid grid-cols-2 gap-2 items-center">
                        <div>
                          <label className="text-xs text-muted-foreground font-mono">
                            Limit
                          </label>
                          <p className="text-[70%] text-muted-foreground">
                            integer &middot; optional &middot; default: 100
                          </p>
                        </div>
                        <Input type="number" defaultValue="100" />
                      </div>
                      <div className="grid grid-cols-2 gap-2 items-center">
                        <div>
                          <label className="text-xs text-muted-foreground font-mono">
                            Search
                          </label>
                          <p className="text-[70%] text-muted-foreground">
                            string &middot; optional &middot; default: ""
                          </p>
                        </div>
                        <Input type="text" defaultValue="" />
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm">
                        <IconPlayerPlay />
                        <span>Run</span>
                      </Button>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        }
      >
        <div className="p-8">
          <CollectionsList />
        </div>
      </Shell>
      <CreateCollection
        open={createCollectionOpen}
        onOpenChange={setCreateCollectionOpen}
      />
    </>
  )
}
