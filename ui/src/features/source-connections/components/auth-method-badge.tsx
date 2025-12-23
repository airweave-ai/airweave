import { Badge } from '@/components/ui/badge'
import type { SourceConnection } from '../data/types'

export function AuthMethodBadge({
  method,
}: {
  method: SourceConnection['authMethod']
}) {
  const methodConfig: Record<
    SourceConnection['authMethod'],
    { label: string; className: string }
  > = {
    oauth_browser: {
      label: 'OAuth',
      className:
        'bg-violet-50 border-violet-200 text-violet-700 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-400',
    },
    oauth_token: {
      label: 'OAuth Token',
      className:
        'bg-violet-50 border-violet-200 text-violet-700 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-400',
    },
    oauth_byoc: {
      label: 'OAuth BYOC',
      className:
        'bg-violet-50 border-violet-200 text-violet-700 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-400',
    },
    direct: {
      label: 'Direct',
      className:
        'bg-slate-50 border-slate-200 text-slate-700 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-400',
    },
    auth_provider: {
      label: 'Auth Provider',
      className:
        'bg-indigo-50 border-indigo-200 text-indigo-700 dark:bg-indigo-950 dark:border-indigo-800 dark:text-indigo-400',
    },
  }

  const config = methodConfig[method]

  return <Badge className={config.className}>{config.label}</Badge>
}
