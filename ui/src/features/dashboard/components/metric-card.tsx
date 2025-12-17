import { Card, CardContent } from '@/components/ui/card'
import { IconArrowDownRight, IconArrowUpRight } from '@tabler/icons-react'

export function MetricCard({
  title,
  value,
  subtitle,
  change,
  trend,
  isError,
}: {
  title: string
  value: string | number
  subtitle: string
  change?: number
  trend?: 'up' | 'down'
  icon: React.ReactNode
  isError?: boolean
}) {
  return (
    <Card className={isError ? 'border-red-200 dark:border-red-900' : ''}>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-muted-foreground uppercase font-mono text-xs">
            <span className="text-sm font-medium">{title}</span>
          </div>
          {change !== undefined && trend && (
            <div
              className={`flex items-center gap-1 text-xs ${trend === 'up' ? 'text-emerald-600' : 'text-red-600'}`}
            >
              {trend === 'up' ? (
                <IconArrowUpRight className="size-3" />
              ) : (
                <IconArrowDownRight className="size-3" />
              )}
              {Math.abs(change)}%
            </div>
          )}
        </div>
        <div className="mt-2">
          <div
            className={`text-3xl font-lighter tabular-nums ${isError ? 'text-red-600' : ''}`}
          >
            {typeof value === 'number' ? value.toLocaleString() : value}
          </div>
          <div className="text-sm text-muted-foreground mt-1">{subtitle}</div>
        </div>
      </CardContent>
    </Card>
  )
}
