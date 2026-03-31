import { MoreVertical } from 'lucide-react';
import {
  IconPencilMinus,
  IconPlayerPause,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';

type CollectionActionsMenuProps = {
  collectionId: string;
};

export function CollectionActionsMenu({
  collectionId: _collectionId,
}: CollectionActionsMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="icon" type="button" variant="ghost">
          <MoreVertical className="size-4" />
          <span className="sr-only">Open collection actions</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="end" className="min-w-47">
        <DropdownMenuItem>
          <IconRefresh />
          Resync
        </DropdownMenuItem>
        <DropdownMenuItem>
          <IconPlayerPause />
          Pause
        </DropdownMenuItem>
        <DropdownMenuItem>
          <IconPencilMinus />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem className="text-destructive">
          <IconTrash /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
