import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/components/ui/input-group'
import { IconPlus, IconSearch } from '@tabler/icons-react'
import { useEffect, useMemo, useRef, useState } from 'react'

interface Source {
  name: string
  slug: string
  description: string
}

interface Category {
  title: string
  sources: Source[]
}

const categories: Category[] = [
  {
    title: 'Databases & Spreadsheets',
    sources: [
      {
        name: 'Airtable',
        slug: 'airtable',
        description: 'Connected workspace for modern teams',
      },
      {
        name: 'Attio',
        slug: 'attio',
        description: 'Flexible CRM for growing teams',
      },
      {
        name: 'Excel',
        slug: 'microsoft',
        description: 'Spreadsheet and data analysis',
      },
      {
        name: 'PostgreSQL',
        slug: 'postgresql',
        description: 'Open-source relational database',
      },
    ],
  },
  {
    title: 'Project & Task Management',
    sources: [
      { name: 'Asana', slug: 'asana', description: 'Work management platform' },
      {
        name: 'ClickUp',
        slug: 'clickup',
        description: 'All-in-one productivity platform',
      },
      {
        name: 'Jira',
        slug: 'atlassian',
        description: 'Issue and project tracking',
      },
      {
        name: 'Linear',
        slug: 'linear',
        description: 'Issue tracking for modern teams',
      },
      { name: 'Monday', slug: 'monday', description: 'Work operating system' },
      {
        name: 'Todoist',
        slug: 'todoist',
        description: 'Task management and to-do lists',
      },
      {
        name: 'Trello',
        slug: 'trello',
        description: 'Visual project management',
      },
    ],
  },
  {
    title: 'Knowledge Base & Documentation',
    sources: [
      {
        name: 'Confluence',
        slug: 'atlassian',
        description: 'Team collaboration and wiki',
      },
      {
        name: 'Notion',
        slug: 'makenotion',
        description: 'All-in-one workspace',
      },
      {
        name: 'OneNote',
        slug: 'microsoft',
        description: 'Digital note-taking',
      },
      {
        name: 'Word',
        slug: 'microsoft',
        description: 'Document editing and collaboration',
      },
      {
        name: 'Google Docs',
        slug: 'google',
        description: 'Cloud-based document editing',
      },
    ],
  },
  {
    title: 'Code Repositories & Dev Tools',
    sources: [
      {
        name: 'GitHub',
        slug: 'github',
        description: 'Code hosting and collaboration',
      },
      {
        name: 'GitLab',
        slug: 'gitlab',
        description: 'DevOps lifecycle platform',
      },
      {
        name: 'Bitbucket',
        slug: 'atlassian',
        description: 'Git code management',
      },
    ],
  },
  {
    title: 'File Storage & Content Management',
    sources: [
      { name: 'Box', slug: 'box', description: 'Cloud content management' },
      {
        name: 'Dropbox',
        slug: 'dropbox',
        description: 'File hosting and sync',
      },
      {
        name: 'Google Drive',
        slug: 'google',
        description: 'Cloud storage and file sharing',
      },
      {
        name: 'OneDrive',
        slug: 'microsoft',
        description: 'Microsoft cloud storage',
      },
      {
        name: 'SharePoint',
        slug: 'microsoft',
        description: 'Enterprise content management',
      },
    ],
  },
  {
    title: 'Email & Calendar',
    sources: [
      { name: 'Gmail', slug: 'google', description: 'Email by Google' },
      {
        name: 'Outlook Mail',
        slug: 'microsoft',
        description: 'Email by Microsoft',
      },
      {
        name: 'Google Calendar',
        slug: 'google',
        description: 'Scheduling and calendar',
      },
      {
        name: 'Outlook Calendar',
        slug: 'microsoft',
        description: 'Calendar by Microsoft',
      },
    ],
  },
  {
    title: 'Team Communication',
    sources: [
      {
        name: 'Slack',
        slug: 'slackhq',
        description: 'Team messaging and channels',
      },
      {
        name: 'Teams',
        slug: 'microsoft',
        description: 'Microsoft collaboration hub',
      },
    ],
  },
  {
    title: 'CRM, Sales & Customer Support',
    sources: [
      {
        name: 'HubSpot',
        slug: 'hubspot',
        description: 'CRM and marketing platform',
      },
      { name: 'Salesforce', slug: 'salesforce', description: 'Enterprise CRM' },
      {
        name: 'Zendesk',
        slug: 'zendesk',
        description: 'Customer service software',
      },
    ],
  },
  {
    title: 'Payments & Finance',
    sources: [
      {
        name: 'Stripe',
        slug: 'stripe',
        description: 'Payment processing platform',
      },
    ],
  },
  {
    title: 'Research & Clinical Data',
    sources: [
      {
        name: 'CTTI AACT',
        slug: 'ctti-clinicaltrials',
        description: 'Clinical trials database',
      },
    ],
  },
]

export const CollectionsList = () => {
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

  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return categories

    const query = searchQuery.toLowerCase()
    return categories
      .map((category) => ({
        ...category,
        sources: category.sources.filter(
          (source) =>
            source.name.toLowerCase().includes(query) ||
            source.description.toLowerCase().includes(query),
        ),
      }))
      .filter((category) => category.sources.length > 0)
  }, [searchQuery])

  const totalSources = useMemo(() => {
    return filteredCategories.reduce(
      (acc, category) => acc + category.sources.length,
      0,
    )
  }, [filteredCategories])

  return (
    <>
      <section className="space-y-6">
        <h2 className="text-md font-medium text-muted-foreground font-mono uppercase">
          Your collections
        </h2>
        <div className="flex gap-4 flex-wrap">
          <Card className="w-[25rem]">
            <CardHeader>
              <CardTitle>Anand's collection</CardTitle>
              <CardDescription className="truncate font-mono text-xs">
                anands-collection-4m6pbv.airweave.ai
              </CardDescription>
              <CardAction>
                <Badge className="bg-emerald-50 border-emerald-300 text-emerald-500">
                  Active
                </Badge>
              </CardAction>
            </CardHeader>
            <CardContent>
              <div className="*:data-[slot=avatar]:ring-background flex -space-x-1 *:data-[slot=avatar]:ring-2">
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
            </CardContent>
          </Card>
          <Button variant="outline" className="flex-col h-28 px-4">
            <IconPlus />
            New
          </Button>
        </div>
      </section>
      <section className="mt-12">
        <header className="flex items-center justify-between">
          <h2 className="text-md font-medium text-muted-foreground font-mono uppercase mb-4">
            Sources
          </h2>
          <div>
            <InputGroup>
              <InputGroupInput
                ref={inputRef}
                placeholder="Press / to search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <InputGroupAddon>
                <IconSearch />
              </InputGroupAddon>
              <InputGroupAddon align="inline-end">
                {totalSources} {totalSources === 1 ? 'source' : 'sources'}
              </InputGroupAddon>
            </InputGroup>
          </div>
        </header>
        {filteredCategories.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            No sources found matching "{searchQuery}"
          </div>
        ) : (
          filteredCategories.map((category) => (
            <div key={category.title} className="mb-10 space-y-4">
              <h3 className="text-sm font-medium text-muted-foreground font-mono uppercase flex items-center gap-2">
                <span>{category.title}</span>
              </h3>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {category.sources.map((source) => (
                  <Card key={source.name}>
                    <CardHeader>
                      <div className="flex items-center gap-2">
                        <Avatar size="sm" className="shrink-0">
                          <AvatarImage
                            src={`https://github.com/${source.slug}.png`}
                            alt={`@${source.slug}`}
                          />
                        </Avatar>
                        <CardTitle className="grow truncate">
                          {source.name}
                        </CardTitle>
                      </div>
                      <CardDescription className="truncate font-mono text-xs">
                        {source.description}
                      </CardDescription>
                      <CardAction>
                        <Button
                          variant="outline"
                          className="rounded-full"
                          size="icon"
                        >
                          <IconPlus />
                        </Button>
                      </CardAction>
                    </CardHeader>
                  </Card>
                ))}
              </div>
            </div>
          ))
        )}
      </section>
    </>
  )
}
