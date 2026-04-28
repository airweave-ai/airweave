import { Plus } from 'lucide-react';
import { Button } from '@/shared/ui/button';
import { DropdownMenuItem } from '@/shared/ui/dropdown-menu';

interface CreateOrganizationSwitcherActionProps {
  onClick: () => void;
}

function CreateOrganizationSwitcherAction({
  onClick,
}: CreateOrganizationSwitcherActionProps) {
  return (
    <div className="p-3">
      <DropdownMenuItem asChild>
        <Button
          className="w-full flex-1 rounded-sm"
          onClick={onClick}
          type="button"
          variant="outline"
        >
          <Plus className="size-4" />
          Create New Organization
        </Button>
      </DropdownMenuItem>
    </div>
  );
}

export { CreateOrganizationSwitcherAction };
