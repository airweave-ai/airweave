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
import { IconPlus } from '@tabler/icons-react'

interface Source {
  name: string
  slug: string
  description: string
}

interface Category {
  icon: string
  title: string
  description: string
  sources: Source[]
}

const categories: Category[] = [
  {
    icon: '📊',
    title: 'Databases & Spreadsheets',
    description: 'Structured data, records, and tables.',
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
    icon: '🗂️',
    title: 'Project & Task Management',
    description: 'Work tracking, planning, and execution.',
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
    icon: '📚',
    title: 'Knowledge Base & Documentation',
    description: 'Docs, wikis, and internal knowledge.',
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
    icon: '🧑‍💻',
    title: 'Code Repositories & Dev Tools',
    description: 'Source control and developer collaboration.',
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
    icon: '☁️',
    title: 'File Storage & Content Management',
    description: 'Files, folders, and document storage.',
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
    icon: '✉️',
    title: 'Email & Calendar',
    description: 'Communication and scheduling.',
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
    icon: '💬',
    title: 'Team Communication',
    description: 'Real-time messaging and collaboration.',
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
    icon: '🧾',
    title: 'CRM, Sales & Customer Support',
    description: 'Customer data, sales pipelines, and support tickets.',
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
    icon: '💳',
    title: 'Payments & Finance',
    description: 'Billing, payments, and transactions.',
    sources: [
      {
        name: 'Stripe',
        slug: 'stripe',
        description: 'Payment processing platform',
      },
    ],
  },
  {
    icon: '🧪',
    title: 'Research & Clinical Data',
    description: 'Specialized research or clinical trial systems.',
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
        <h2 className="text-md font-medium text-muted-foreground font-mono uppercase mb-8">
          Sources
        </h2>
        {categories.map((category) => (
          <div key={category.title} className="mb-10">
            <h3 className="text-sm font-medium text-muted-foreground font-mono uppercase mb-2 flex items-center gap-2">
              <span>{category.icon}</span>
              <span>{category.title}</span>
            </h3>
            <p className="text-xs text-muted-foreground mb-4">
              {category.description}
            </p>
            <div className="flex gap-4 flex-wrap">
              {category.sources.map((source) => (
                <Card key={source.name} className="w-[25rem]">
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
        ))}
      </section>
    </>
  )
}
