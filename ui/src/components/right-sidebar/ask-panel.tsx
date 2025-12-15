'use client'

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
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
  PromptInputButton,
  PromptInputFooter,
  type PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from '@/components/ai-elements/prompt-input'
import { Suggestion, Suggestions } from '@/components/ai-elements/suggestion'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { IconMicrophone, IconSparkles } from '@tabler/icons-react'
import { nanoid } from 'nanoid'
import { useCallback, useState } from 'react'

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

const suggestions = [
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

export function AskPanel() {
  const [text, setText] = useState('')
  const [model, setModel] = useState(models[0].id)
  const [useMicrophone, setUseMicrophone] = useState(false)
  const [status, setStatus] = useState<
    'submitted' | 'streaming' | 'ready' | 'error'
  >('ready')
  const [messages, setMessages] = useState<MessageType[]>([])

  const selectedModel = models.find((m) => m.id === model)

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
    <div className="flex size-full flex-col text-foreground">
      <Conversation className="flex-1">
        <ConversationContent className="gap-4 p-0">
          {messages.length === 0 ? (
            <ConversationEmptyState
              title="Ask about Airweave"
              description="Get help with data sources, syncs, and more"
              icon={<IconSparkles className="size-8" strokeWidth={1.1} />}
            />
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
        {messages.length === 0 && (
          <Suggestions className="mb-3">
            {suggestions.map((suggestion) => (
              <Suggestion
                key={suggestion}
                onClick={() => handleSuggestionClick(suggestion)}
                suggestion={suggestion}
              />
            ))}
          </Suggestions>
        )}
        <PromptInput onSubmit={handleSubmit} multiple className="mt-2.5">
          <PromptInputBody>
            <PromptInputTextarea
              placeholder="Ask about Airweave..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="min-h-10"
            />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputTools>
              <PromptInputButton
                onClick={() => setUseMicrophone(!useMicrophone)}
                variant={useMicrophone ? 'default' : 'ghost'}
              >
                <IconMicrophone className="size-4" />
                <span className="sr-only">Voice</span>
              </PromptInputButton>
              <Select value={model} onValueChange={(v) => v && setModel(v)}>
                <SelectTrigger className="h-8 w-auto gap-1 border-none bg-transparent px-2 text-xs shadow-none hover:bg-accent">
                  <SelectValue>{selectedModel?.name}</SelectValue>
                </SelectTrigger>
                <SelectContent className="w-48">
                  {models.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
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
  )
}
