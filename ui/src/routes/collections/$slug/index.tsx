'use client'

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  IconAdjustmentsAlt,
  IconBrandOpenai,
  IconCode,
  IconEditCircle,
  IconPencil,
  IconPlug,
} from '@tabler/icons-react'
import { createFileRoute } from '@tanstack/react-router'
import { nanoid } from 'nanoid'
import { useCallback, useMemo, useState } from 'react'
import { ChainOfThoughtDemo } from '@/features/collection-detail/components/chain-of-thought-demo'
import { DocsSidebar } from '@/features/collection-detail/components/docs-sidebar'
import { SearchSettings } from '@/features/collection-detail/components/search-settings'
import {
  askSuggestions,
  collection,
  defaultSuggestions,
  fallbackResponses,
  mockResponses,
  models,
} from '@/features/collection-detail/data/mock-data'
import type { MessageType } from '@/features/collection-detail/data/types'

export const Route = createFileRoute('/collections/$slug/')({
  component: CollectionDetailPage,
})

function CollectionDetailPage() {
  const [createCollectionOpen, setCreateCollectionOpen] = useState(false)
  const [text, setText] = useState('')
  const [model, setModel] = useState(models[0].id)
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

  return (
    <Shell
      askTitle={collection.name}
      askDescription="Ask questions about your connected data sources."
      askSuggestions={askSuggestions}
      docs={<DocsSidebar />}
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
                      <ChainOfThoughtDemo />
                    ) : (
                      messages.map((message) => (
                        <Message from={message.from} key={message.key}>
                          <MessageContent>
                            {message.from === 'assistant' ? (
                              <MessageResponse>{message.content}</MessageResponse>
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
                  <PromptInput onSubmit={handleSubmit} multiple className="mt-4">
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
          <SearchSettings />
        </div>
      </div>
      <CreateCollection
        open={createCollectionOpen}
        onOpenChange={setCreateCollectionOpen}
      />
    </Shell>
  )
}
