import { Badge } from '@/components/ui/badge'
import { IconLoader2 } from '@tabler/icons-react'
import type { Collection } from '../data/types'

export function StatusBadge({ status }: { status: Collection['status'] }) {
  const statusConfig = {
    active: {
      indicator: <span className="size-1.5 rounded-full bg-emerald-500" />,
      badge:
        'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-400',
      label: 'Active',
    },
    syncing: {
      indicator: <IconLoader2 className="size-3 animate-spin" />,
      badge:
        'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-400',
      label: 'Syncing',
    },
    paused: {
      indicator: <span className="size-1.5 rounded-full bg-gray-400" />,
      badge:
        'bg-gray-50 border-gray-200 text-gray-600 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400',
      label: 'Paused',
    },
  }

  const config = statusConfig[status]

  return (
    <Badge className={`${config.badge} gap-1.5`}>
      {config.indicator}
      {config.label}
    </Badge>
  )
}
