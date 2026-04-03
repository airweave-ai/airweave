import { useNavigate } from '@tanstack/react-router';
import { Button } from '@/shared/ui/button';

export function CreateCollectionButton({
  children,
  ...props
}: Omit<React.ComponentProps<typeof Button>, 'asChild' | 'type'>) {
  const navigate = useNavigate();

  return (
    <Button
      {...props}
      type="button"
      onClick={() =>
        void navigate({
          search: ((prev: Record<string, unknown>) => ({
            ...prev,
            dialog: { type: 'create-collection' },
          })) as never,
        })
      }
    >
      {children}
    </Button>
  );
}
