import * as React from 'react';
import { IconPlayerPause, IconRefresh, IconTrash } from '@tabler/icons-react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { ButtonGroup, ButtonGroupSeparator } from '@/shared/ui/button-group';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';

type CollectionBulkActionsMenuProps = {
  collectionIds: Array<string>;
};

export function CollectionBulkActionsMenu({
  collectionIds: _collectionIds,
}: CollectionBulkActionsMenuProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <ButtonGroup>
      <Button
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((currentOpen) => !currentOpen)}
        type="button"
        variant="secondary"
        className="border-r-0"
      >
        Bulk actions
      </Button>
      <ButtonGroupSeparator />
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            aria-label="Open bulk actions menu"
            type="button"
            size="icon"
            variant="secondary"
          >
            <ChevronDown
              className={cn(
                'size-4 text-muted-foreground transition-transform',
                open && 'rotate-180',
              )}
              data-role="indicator"
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="center" className="min-w-47" side="bottom">
          <DropdownMenuItem>
            <IconRefresh />
            Resync
          </DropdownMenuItem>
          <DropdownMenuItem>
            <IconPlayerPause />
            Pause
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive">
            <IconTrash /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </ButtonGroup>
  );
}
