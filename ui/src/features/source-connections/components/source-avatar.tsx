import { Avatar, AvatarImage } from '@/components/ui/avatar'
import { sourceSlugMap } from '../data/mock-connections'

export function SourceAvatar({ shortName }: { shortName: string }) {
  return (
    <div className="flex items-center gap-2">
      <Avatar size="sm">
        <AvatarImage
          src={`https://github.com/${sourceSlugMap[shortName] || shortName}.png`}
          alt={shortName}
        />
      </Avatar>
      <span className="capitalize">{shortName}</span>
    </div>
  )
}
