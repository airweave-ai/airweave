import { Link } from '@tanstack/react-router';
import { Button } from '@/shared/ui/button';

export function CreateCollectionButton({
  children,
  ...props
}: Omit<React.ComponentProps<typeof Button>, 'asChild' | 'type'>) {
  return (
    <Button {...props} type="button" asChild>
      <Link
        to="."
        search={(prev) => ({ ...prev, dialog: { type: 'create-collection' } })}
      >
        {children}
      </Link>
    </Button>
  );
}
