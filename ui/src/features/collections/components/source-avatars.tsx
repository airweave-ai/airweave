import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { sourceSlugMap } from '../data/mock-collections'

export function SourceAvatars({ sources }: { sources: string[] }) {
  return (
    <div className="flex -space-x-1.5 *:ring-2 *:ring-background">
      {sources.slice(0, 4).map((source) => (
        <Avatar key={source} size="sm">
          <AvatarImage
            src={`https://github.com/${sourceSlugMap[source] || source}.png`}
            alt={source}
          />
        </Avatar>
      ))}
      {sources.length > 4 && (
        <div className="flex items-center justify-center size-6 rounded-full bg-muted text-[10px] font-medium text-muted-foreground ring-2 ring-background">
          +{sources.length - 4}
        </div>
      )}
    </div>
  )
}
