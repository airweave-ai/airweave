'use client'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { cn } from '@/lib/utils'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface ApiEndpoint {
  method: HttpMethod
  name: string
  path: string
  request?: object
  response: object
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
    name: 'List',
    path: '/api/connections',
    response: {
      data: [
        {
          id: 'conn_abc123',
          name: 'My Connection',
          source: 'notion',
          status: 'active',
          created_at: '2024-01-15T09:30:00Z',
        },
        {
          id: 'conn_def456',
          name: 'Another Connection',
          source: 'slack',
          status: 'active',
          created_at: '2024-01-16T14:20:00Z',
        },
      ],
      total: 2,
      page: 1,
      per_page: 20,
    },
  },
  {
    method: 'GET',
    name: 'Get',
    path: '/api/connections/:id',
    response: {
      id: 'conn_abc123',
      name: 'My Connection',
      source: 'notion',
      status: 'active',
      config: {
        workspace_id: 'ws_12345',
        sync_frequency: 'hourly',
      },
      created_at: '2024-01-15T09:30:00Z',
      updated_at: '2024-01-15T09:30:00Z',
    },
  },
  {
    method: 'POST',
    name: 'Search',
    path: '/api/connections/search',
    request: {
      query: 'notion',
      filters: {
        status: ['active', 'pending'],
        source: ['notion', 'slack'],
      },
      sort: {
        field: 'created_at',
        order: 'desc',
      },
      page: 1,
      per_page: 20,
    },
    response: {
      data: [
        {
          id: 'conn_abc123',
          name: 'My Notion Connection',
          source: 'notion',
          status: 'active',
        },
      ],
      total: 1,
      page: 1,
      per_page: 20,
    },
  },
  {
    method: 'POST',
    name: 'Create',
    path: '/api/connections',
    request: {
      name: 'New Connection',
      source: 'notion',
      config: {
        workspace_id: 'ws_12345',
        sync_frequency: 'hourly',
      },
    },
    response: {
      id: 'conn_xyz789',
      name: 'New Connection',
      source: 'notion',
      status: 'pending',
      config: {
        workspace_id: 'ws_12345',
        sync_frequency: 'hourly',
      },
      created_at: '2024-01-20T10:00:00Z',
    },
  },
  {
    method: 'POST',
    name: 'Refresh All Source Connections',
    path: '/api/connections/refresh',
    request: {
      source: 'notion',
      force: true,
    },
    response: {
      message: 'Refresh initiated',
      connections_affected: 5,
      job_id: 'job_abc123',
      estimated_duration: '5 minutes',
    },
  },
  {
    method: 'DELETE',
    name: 'Delete',
    path: '/api/connections/:id',
    response: {
      success: true,
      message: 'Connection deleted successfully',
      deleted_at: '2024-01-20T12:00:00Z',
    },
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

function CodeBlock({ title, code }: { title: string; code: object }) {
  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <div className="bg-muted/50 px-3 py-1.5 border-b border-border/50">
        <span className="text-xs font-medium text-muted-foreground">
          {title}
        </span>
      </div>
      <pre className="p-3 overflow-x-auto bg-muted/20">
        <code className="text-xs font-mono text-foreground/90 leading-relaxed">
          {JSON.stringify(code, null, 2)}
        </code>
      </pre>
    </div>
  )
}

export function CodePanel() {
  return (
    <Accordion>
      {endpoints.map((endpoint, index) => (
        <AccordionItem key={index} className="border-border/40">
          <AccordionTrigger className="hover:no-underline group">
            <div className="flex items-center gap-2.5">
              <MethodBadge method={endpoint.method} />
              <span className="text-sm font-medium">{endpoint.name}</span>
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-3 pt-1">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Endpoint:</span>
                <code className="bg-muted/50 px-2 py-0.5 rounded font-mono text-foreground/80">
                  {endpoint.path}
                </code>
              </div>
              <div className="space-y-2.5">
                {endpoint.request && (
                  <CodeBlock title="Request Body" code={endpoint.request} />
                )}
                <CodeBlock title="Response" code={endpoint.response} />
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  )
}
