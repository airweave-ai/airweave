'use client'

import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtSearchResult,
  ChainOfThoughtSearchResults,
  ChainOfThoughtStep,
} from '@/components/ai-elements/chain-of-thought'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import {
  InlineCitation,
  InlineCitationCard,
  InlineCitationCardBody,
  InlineCitationCardTrigger,
  InlineCitationCarousel,
  InlineCitationCarouselHeader,
  InlineCitationCarouselIndex,
  InlineCitationCarouselNext,
  InlineCitationCarouselPrev,
  InlineCitationText,
} from '@/components/ai-elements/inline-citation'
import {
  Message,
  MessageContent,
  MessageResponse,
} from '@/components/ai-elements/message'
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  type PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from '@/components/ai-elements/prompt-input'
import { CreateCollection } from '@/components/create-collection'
import { Shell } from '@/components/shell'
import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  IconAdjustmentsAlt,
  IconBrain,
  IconBrandOpenai,
  IconChevronRight,
  IconCode,
  IconCopy,
  IconEditCircle,
  IconExternalLink,
  IconFilter,
  IconFilterOff,
  IconMarkdown,
  IconMenu2,
  IconPencil,
  IconPlug,
  IconSearch,
  IconSortDescending,
  IconSparkles,
  IconTextSize,
  IconThumbDown,
  IconThumbUp,
  IconWriting,
  IconZoomOut,
  IconZoomPan,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import { nanoid } from 'nanoid'
import { useCallback, useMemo, useState } from 'react'

export const Route = createFileRoute('/collections/$slug')({
  component: CollectionDetailPage,
})

interface SourceConnection {
  name: string
  slug: string
  connected: boolean
}

interface EntityType {
  name: string
  count: number
}

interface Collection {
  id: string
  name: string
  status: 'active' | 'syncing' | 'paused'
  sources: SourceConnection[]
  schedule: string
  lastSync: string
  entities: {
    total: number
    types: EntityType[]
  }
}

const collection: Collection = {
  id: 'anands-collection-4m6pbv',
  name: "Anand's collection 123",
  status: 'active',
  sources: [
    { name: 'Notion Connection', slug: 'makenotion', connected: true },
    { name: 'Asana Connection', slug: 'asana', connected: true },
    { name: 'Linear Connection', slug: 'linear', connected: true },
  ],
  schedule: 'Daily 2:29pm (Now)',
  lastSync: '23h ago',
  entities: {
    total: 0,
    types: [
      { name: 'NotionDatabase', count: 0 },
      { name: 'NotionFile', count: 0 },
      { name: 'NotionPage', count: 0 },
      { name: 'NotionProperty', count: 0 },
    ],
  },
}

const askSuggestions = [
  'How do I search this collection?',
  'How do I add more sources?',
  'What entity types are available?',
]

type MessageType = {
  key: string
  from: 'user' | 'assistant'
  content: string
}

const models = [
  { id: 'gpt-5.2', name: 'GPT-5.2', provider: 'OpenAI' },
  { id: 'claude-opus-4.5', name: 'Claude Opus 4.5', provider: 'Anthropic' },
  { id: 'claude-sonnet-4.5', name: 'Claude Sonnet 4.5', provider: 'Anthropic' },
  { id: 'gemini-3-pro', name: 'Gemini 3 Pro', provider: 'Google' },
]

const defaultSuggestions = [
  'How do I connect a data source?',
  'What integrations are available?',
  'How do I create a sync?',
  'Explain the data pipeline',
]

const mockResponses: Record<string, string> = {
  'How do I connect a data source?': `## Connecting a Data Source

To connect a data source in Airweave:

1. Navigate to **Sources** in the sidebar
2. Click **Add Source** to see available integrations
3. Select your data source type (API, Database, etc.)
4. Enter your credentials and configure the connection
5. Test the connection to verify it works

Would you like me to explain any specific data source?`,
  'What integrations are available?': `## Available Integrations

Airweave supports many popular integrations:

**APIs & Services**
- REST APIs
- GraphQL endpoints
- Webhooks

**Databases**
- PostgreSQL
- MySQL
- MongoDB

**Cloud Services**
- AWS S3
- Google Cloud
- Azure Blob

Check the **Sources** page for the complete list!`,
  'How do I create a sync?': `## Creating a Sync

To create a sync between data sources:

1. Go to **Syncs** in the navigation
2. Click **New Sync**
3. Select your source and destination
4. Configure mapping rules
5. Set the sync schedule (real-time, hourly, daily)
6. Save and activate the sync

The sync will begin automatically based on your schedule.`,
  'Explain the data pipeline': `## Airweave Data Pipeline

The data pipeline consists of:

**1. Sources**
Connect to your data origins (APIs, databases, files)

**2. Transformations**
Apply rules to clean and format your data

**3. Destinations**
Send processed data to target systems

**4. Monitoring**
Track sync status, errors, and performance

Each step is configurable and can be monitored in real-time.`,
}

const fallbackResponses = [
  `That's a great question! Airweave makes it easy to connect and sync your data. You can explore the **Sources** page to see available integrations, or check the **Syncs** section to manage your data flows.`,
  `I'd be happy to help with that! For detailed information, you can check the documentation or explore the sidebar navigation to find the relevant section.`,
  `Good question! Airweave provides flexible options for data integration. Feel free to explore the interface or ask about specific features.`,
]

function CollectionDetailPage() {
  const [createCollectionOpen, setCreateCollectionOpen] = useState(false)
  const [text, setText] = useState('')
  const [model, setModel] = useState(models[0].id)
  const [useMicrophone, setUseMicrophone] = useState(false)
  const [status, setStatus] = useState<
    'submitted' | 'streaming' | 'ready' | 'error'
  >('ready')
  const [messages, setMessages] = useState<MessageType[]>([])

  const selectedModel = models.find((m) => m.id === model)
  const suggestionsToShow = useMemo(
    () =>
      askSuggestions && askSuggestions.length > 0
        ? askSuggestions
        : defaultSuggestions,
    [],
  )

  const streamResponse = useCallback(
    async (messageId: string, content: string) => {
      setStatus('streaming')
      const words = content.split(' ')
      let currentContent = ''
      for (let i = 0; i < words.length; i++) {
        currentContent += (i > 0 ? ' ' : '') + words[i]
        setMessages((prev) =>
          prev.map((msg) =>
            msg.key === messageId ? { ...msg, content: currentContent } : msg,
          ),
        )
        await new Promise((resolve) =>
          setTimeout(resolve, Math.random() * 50 + 20),
        )
      }
      setStatus('ready')
    },
    [],
  )

  const addUserMessage = useCallback(
    (content: string) => {
      const userMessage: MessageType = {
        key: `user-${nanoid()}`,
        from: 'user',
        content,
      }
      setMessages((prev) => [...prev, userMessage])

      setTimeout(() => {
        const assistantMessageId = `assistant-${nanoid()}`
        const response =
          mockResponses[content] ||
          fallbackResponses[
            Math.floor(Math.random() * fallbackResponses.length)
          ]
        const assistantMessage: MessageType = {
          key: assistantMessageId,
          from: 'assistant',
          content: '',
        }
        setMessages((prev) => [...prev, assistantMessage])
        streamResponse(assistantMessageId, response)
      }, 400)
    },
    [streamResponse],
  )

  const handleSubmit = (message: PromptInputMessage) => {
    if (!message.text?.trim()) return
    setStatus('submitted')
    addUserMessage(message.text)
    setText('')
  }

  const handleSuggestionClick = (suggestion: string) => {
    setStatus('submitted')
    addUserMessage(suggestion)
  }

  return (
    <Shell
      askTitle={collection.name}
      askDescription="Ask questions about your connected data sources."
      askSuggestions={askSuggestions}
      docs={
        <div className="flex flex-col h-full">
          <header className="border-b shrink-0 px-4 py-2 flex justify-between items-center gap-3">
            <div className="shrink-0 flex gap-2">
              <Button variant="outline" size="icon">
                <IconMenu2 />
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
          <article className="p-4 space-y-4 grow opacity-80">
            <p>
              A <strong className="font-medium">Collection</strong> is a
              searchable knowledge base made up of synced data from one or more
              source connections. When you search a collection, queries run
              across all entities from all its connected sources.
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
              <strong className="font-medium">
                Search settings explained:
              </strong>
            </p>
            <p>
              <ul className="list-disc list-inside space-y-4">
                <li>
                  <strong className="font-medium">Search Method</strong>: pick
                  how results are ranked. Hybrid blends semantic vectors with
                  keywords, Neural is semantic-only, and Keyword sticks to exact
                  text matches.
                </li>
                <li>
                  <strong className="font-medium">Query Expansion</strong>:
                  rewrites or augments the query with synonyms/related terms to
                  widen recall. Turn off for precise lookups.
                </li>
                <li>
                  <strong className="font-medium">Query Interpretation</strong>:
                  lets the system infer intent (filters, entities, date ranges)
                  from natural language before searching. Disable to run the
                  literal text.
                </li>
                <li>
                  <strong className="font-medium">AI Reranking</strong>: uses an
                  LLM to reorder the top candidates from search so the most
                  relevant answers appear first.
                </li>
                <li>
                  <strong className="font-medium">Recency Bias</strong>:
                  increases the weight of newer items. Higher values favor fresh
                  content; lower values prefer overall relevance.
                </li>
                <li>
                  <strong className="font-medium">Metadata Filtering</strong>:
                  JSON filters applied before search (e.g.,{' '}
                  {`{"author":"alice","type":"doc"}`}) to scope results to
                  specific attributes.
                </li>
              </ul>
            </p>
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
    >
      <div className="grow">
        <header className="flex items-center gap-8 border-b border-muted px-6 py-2.5">
          <h1 className="font-mono uppercase text-sm font-semibold">
            {collection.name}
          </h1>
          <Tabs>
            <TabsList className="mt-0 w-full">
              <TabsTrigger value="hybrid">
                <IconEditCircle />
                <span>Playground</span>
              </TabsTrigger>
              <TabsTrigger value="keyword">
                <IconPlug />
                <span>Source Connections</span>
              </TabsTrigger>
              <TabsTrigger value="settings">
                <IconAdjustmentsAlt />
                <span>Settings</span>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="ml-auto flex items-center gap-2">
            <Tabs>
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
            </Tabs>
          </div>
        </header>

        <div className="w-full h-full flex">
          <div className="grow h-full">
            <div className="p-6 space-y-6 w-full max-w-3xl mx-auto">
              <div className="flex size-full flex-col text-foreground">
                <Conversation className="flex-1">
                  <ConversationContent className="gap-4 p-0">
                    {messages.length === 0 ? (
                      // <ConversationEmptyState
                      //   className="py-76"
                      //   title={`Ask about ${collection.name}`}
                      //   description="Ask questions about your connected data sources."
                      //   icon={
                      //     <IconSparkles className="size-8" strokeWidth={1.1} />
                      //   }
                      // />
                      <ChainOfThought defaultOpen>
                        <div className="flex justify-end pt-62">
                          <div className="bg-primary text-sm text-primary-foreground rounded-xl p-4">
                            Who is the main character in the story?
                          </div>
                        </div>
                        <ChainOfThoughtContent>
                          <ChainOfThoughtStep
                            icon={IconZoomPan}
                            label="Query Expansion"
                            status="complete"
                          >
                            <ChainOfThoughtSearchResults>
                              {[
                                'Identify the protagonist of the story.',
                                'What is the lead character in this narrative?',
                                'Name the primary figure in the plot.',
                                'Show the main character details.',
                              ].map((alt) => (
                                <ChainOfThoughtSearchResult key={alt}>
                                  {alt}
                                </ChainOfThoughtSearchResult>
                              ))}
                            </ChainOfThoughtSearchResults>
                          </ChainOfThoughtStep>

                          <ChainOfThoughtStep
                            icon={IconSearch}
                            label="Retrieval · hybrid (5 neural, 5 BM25 embeddings)"
                            status="complete"
                            className="relative"
                          >
                            <Button
                              size="xs"
                              variant="secondary"
                              className="absolute top-0 right-0"
                            >
                              Entities
                              <IconChevronRight />
                            </Button>
                            <ChainOfThoughtSearchResults>
                              {[
                                'Embeddings dim: 3072',
                                'Retrieved 1,000 candidate results',
                              ].map((detail) => (
                                <ChainOfThoughtSearchResult key={detail}>
                                  {detail}
                                </ChainOfThoughtSearchResult>
                              ))}
                            </ChainOfThoughtSearchResults>
                          </ChainOfThoughtStep>

                          <ChainOfThoughtStep
                            icon={IconSortDescending}
                            label="AI reranking top 1,000 results"
                            status="complete"
                          >
                            <ChainOfThoughtSearchResults>
                              {[
                                '#1: Result 668 (relevance: 0.09)',
                                '#2: Result 120 (relevance: 0.09)',
                                '#3: Result 500 (relevance: 0.08)',
                                '#4: Result 987 (relevance: 0.08)',
                                '#5: Result 539 (relevance: 0.07)',
                              ].map((result) => (
                                <ChainOfThoughtSearchResult key={result}>
                                  {result}
                                </ChainOfThoughtSearchResult>
                              ))}
                            </ChainOfThoughtSearchResults>
                          </ChainOfThoughtStep>

                          <ChainOfThoughtStep
                            icon={IconWriting}
                            label="Answer generation"
                            status="active"
                          >
                            <div className="bg-muted/50 rounded-xl p-4">
                              The main character appearing throughout the
                              excerpts is Carlo Badini, the co-founder and CEO
                              of FirstQuadrant. He is referenced in multiple
                              items (e.g., the contact list showing{' '}
                              <InlineCitation>
                                <InlineCitationText>
                                  “Carlo Badini”
                                </InlineCitationText>
                                <InlineCitationCard>
                                  <InlineCitationCardTrigger
                                    sources={['https://Linear.com']}
                                  />
                                  <InlineCitationCardBody>
                                    <InlineCitationCarousel>
                                      <InlineCitationCarouselHeader>
                                        <InlineCitationCarouselPrev />
                                        <InlineCitationCarouselNext />
                                        <InlineCitationCarouselIndex />
                                      </InlineCitationCarouselHeader>
                                    </InlineCitationCarousel>
                                  </InlineCitationCardBody>
                                </InlineCitationCard>
                              </InlineCitation>{' '}
                              and comments/notes that mention his actions and{' '}
                              <InlineCitation>
                                <InlineCitationText>
                                  messages
                                </InlineCitationText>
                                <InlineCitationCard>
                                  <InlineCitationCardTrigger
                                    sources={['https://Linear.com']}
                                  />
                                  <InlineCitationCardBody>
                                    <InlineCitationCarousel>
                                      <InlineCitationCarouselHeader>
                                        <InlineCitationCarouselPrev />
                                        <InlineCitationCarouselNext />
                                        <InlineCitationCarouselIndex />
                                      </InlineCitationCarouselHeader>
                                    </InlineCitationCarousel>
                                  </InlineCitationCardBody>
                                </InlineCitationCard>
                              </InlineCitation>
                              ).
                            </div>
                          </ChainOfThoughtStep>
                        </ChainOfThoughtContent>
                      </ChainOfThought>
                    ) : (
                      messages.map((message) => (
                        <Message from={message.from} key={message.key}>
                          <MessageContent>
                            {message.from === 'assistant' ? (
                              <MessageResponse>
                                {message.content}
                              </MessageResponse>
                            ) : (
                              message.content
                            )}
                          </MessageContent>
                        </Message>
                      ))
                    )}
                  </ConversationContent>
                  <ConversationScrollButton />
                </Conversation>

                <div className="shrink-0">
                  <PromptInput
                    onSubmit={handleSubmit}
                    multiple
                    className="mt-4"
                  >
                    <PromptInputBody>
                      <PromptInputTextarea
                        placeholder="Ask a question about your data..."
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                      />
                    </PromptInputBody>
                    <PromptInputFooter className="p-1 pt-0">
                      <PromptInputTools>
                        <Select
                          value={model}
                          onValueChange={(v) => v && setModel(v)}
                        >
                          <SelectTrigger className="h-8 w-auto gap-1 border-none bg-transparent px-2 text-xs shadow-none hover:bg-accent">
                            <SelectValue className="flex items-center gap-1">
                              <IconBrandOpenai strokeWidth={1.5} />
                              {selectedModel?.name}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent className="w-48">
                            {models.map((m) => (
                              <SelectItem key={m.id} value={m.id}>
                                {m.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Select>
                          <SelectTrigger className="h-8 w-auto gap-1 border-none bg-transparent px-2 text-xs shadow-none hover:bg-accent -translate-x-4">
                            <div className="*:data-[slot=avatar]:ring-background flex -space-x-1 *:data-[slot=avatar]:ring-2 scale-75 translate-x-1">
                              <Avatar size="sm">
                                <AvatarImage
                                  src="https://github.com/makenotion.png"
                                  alt="@makenotion"
                                />
                              </Avatar>
                              <Avatar size="sm">
                                <AvatarImage
                                  src="https://github.com/asana.png"
                                  alt="@asana"
                                />
                              </Avatar>
                              <Avatar size="sm">
                                <AvatarImage
                                  src="https://github.com/linear.png"
                                  alt="@linear"
                                />
                              </Avatar>
                            </div>
                            <SelectValue>All Sources</SelectValue>
                          </SelectTrigger>
                        </Select>
                      </PromptInputTools>
                      <PromptInputSubmit
                        disabled={status === 'streaming'}
                        status={status}
                      />
                    </PromptInputFooter>
                  </PromptInput>
                  <div className="flex items-center justify-center mt-2 gap-1.5 text-[70%] opacity-50">
                    <div>Powered by</div>
                    <img
                      src="https://app.airweave.ai/logo-airweave-lightbg.svg"
                      alt="Airweave"
                      className="h-3"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-muted/20 p-4 border-l border-muted gap-4 flex flex-col">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">Search Method</Label>
              <Tabs>
                <TabsList className="mt-0 w-full">
                  <TabsTrigger value="hybrid">
                    <IconSparkles />
                    <span>Hybrid</span>
                  </TabsTrigger>
                  <TabsTrigger value="neural">
                    <IconBrain />
                    <span>Neural</span>
                  </TabsTrigger>
                  <TabsTrigger value="keyword">
                    <IconTextSize />
                    <span>Keyword</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">Query Expansion</Label>
              <Tabs>
                <TabsList className="mt-0 w-full">
                  <TabsTrigger value="hybrid">
                    <IconZoomPan />
                    <span>On</span>
                  </TabsTrigger>
                  <TabsTrigger value="neural">
                    <IconZoomOut />
                    <span>Off</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">Query Interpretation</Label>
              <Tabs>
                <TabsList className="mt-0 w-full">
                  <TabsTrigger value="hybrid">
                    <IconFilter />
                    <span>On</span>
                  </TabsTrigger>
                  <TabsTrigger value="neural">
                    <IconFilterOff />
                    <span>Off</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">AI Reranking</Label>
              <Tabs>
                <TabsList className="mt-0 w-full">
                  <TabsTrigger value="hybrid">
                    <IconSortDescending />
                    <span>On</span>
                  </TabsTrigger>
                  <TabsTrigger value="neural">
                    <IconMenu2 />
                    <span>Off</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2 text-xs justify-between">
                <Label className="text-xs">Recency Bias</Label>
                <div className="font-mono">0.2</div>
              </div>
              <div className="flex items-center gap-2.5 text-xs w-66 bg-muted py-2 px-3 text-muted-foreground font-mono rounded-lg">
                <div>0</div>
                <Slider />
                <div>1</div>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2 text-xs justify-between">
                <Label className="text-xs">Metadata Filtering</Label>
              </div>
              <Textarea className="bg-card font-mono" placeholder="{}" />
            </div>
          </div>
        </div>
      </div>
      <CreateCollection
        open={createCollectionOpen}
        onOpenChange={setCreateCollectionOpen}
      />
    </Shell>
  )
}
