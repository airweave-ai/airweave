import { ChevronDown } from 'lucide-react';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { ButtonGroup } from '@/shared/ui/button-group';

type CollectionFilterButtonGroupProps = {
  label: string;
  value?: string;
  className?: string;
};

export function CollectionFilterButtonGroup({
  label,
  value = 'All',
  className,
}: CollectionFilterButtonGroupProps) {
  return (
    <ButtonGroup className={cn('shrink-0', className)}>
      <Button type="button" variant="outline">
        {label}: {value}
      </Button>
      <Button
        aria-label={`Open ${label.toLowerCase()} filter`}
        size="icon"
        type="button"
        variant="outline"
      >
        <ChevronDown className="size-4 text-muted-foreground" />
      </Button>
    </ButtonGroup>
  );
}
