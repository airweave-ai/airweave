import { Badge } from '@/components/ui/badge'
import { IconAlertCircle, IconKey, IconLoader2 } from '@tabler/icons-react'

export function StatusBadge({
  status,
}: {
  status: 'active' | 'syncing' | 'error' | 'pending_auth'
}) {
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
    error: {
      indicator: <IconAlertCircle className="size-3" />,
      badge:
        'bg-red-50 border-red-200 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-400',
      label: 'Error',
    },
    pending_auth: {
      indicator: <IconKey className="size-3" />,
      badge:
        'bg-orange-50 border-orange-200 text-orange-700 dark:bg-orange-950 dark:border-orange-800 dark:text-orange-400',
      label: 'Auth Required',
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
