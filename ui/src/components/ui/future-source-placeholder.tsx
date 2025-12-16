import { cn } from '@/lib/utils'
import { IconPlus } from '@tabler/icons-react'

interface FutureSourcePlaceholderProps {
  className?: string
}

export function FutureSourcePlaceholder({
  className,
}: FutureSourcePlaceholderProps) {
  return (
    <div
      className={cn('aspect-square p-4 bg-white/70 dark:bg-zinc-800/70', className)}
    >
      <div className="w-full h-full flex flex-col items-center justify-center">
        <div className="w-20 h-20 rounded-2xl border-2 border-dashed flex items-center justify-center border-zinc-350 dark:border-zinc-600">
          <IconPlus className="w-8 h-8 opacity-35 text-zinc-350 dark:text-zinc-500" />
        </div>
        <div className="text-[10px] font-mono opacity-35 mt-2 text-zinc-400 dark:text-zinc-500">
          future source
        </div>
      </div>
    </div>
  )
}
