import { useForm } from '@tanstack/react-form';
import * as z from 'zod';
import { useCreateApiKeyMutation } from '../api';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';
import { Field, FieldError, FieldLabel } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';

const createApiKeyFormSchema = z.object({
  expiration_days: z.int().min(1).max(365),
  name: z.string().optional(),
});

const expirationDayOptions = [30, 60, 90, 180, 365] as const;

type CreateApiKeyFormInput = z.input<typeof createApiKeyFormSchema>;

const defaultFormValues: CreateApiKeyFormInput = {
  expiration_days: 90,
  name: '',
};

type CreateApiKeyDialogProps = {
  onClose: () => void;
};

export function CreateApiKeyDialog({ onClose }: CreateApiKeyDialogProps) {
  const createApiKeyMutation = useCreateApiKeyMutation();

  const form = useForm({
    defaultValues: defaultFormValues,
    validators: {
      onSubmit: createApiKeyFormSchema,
    },
    onSubmit: ({ value }) => {
      createApiKeyMutation.mutate(
        {
          // TODO: Send `name` once the API supports storing API key labels.
          body: { expiration_days: value.expiration_days },
        },
        {
          onSuccess: onClose,
        },
      );
    },
  });

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="bg-background [view-transition-name:app-dialog-transition]"
      >
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void form.handleSubmit();
          }}
        >
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
          </DialogHeader>

          <form.Field name="expiration_days">
            {(field) => (
              <Field data-invalid={!field.state.meta.isValid}>
                <FieldLabel htmlFor={field.name}>
                  Choose how long this key should remain valid
                </FieldLabel>
                <Select
                  value={field.state.value.toString()}
                  onValueChange={(value) =>
                    field.handleChange(parseInt(value, 10))
                  }
                >
                  <SelectTrigger
                    id={field.name}
                    aria-invalid={!field.state.meta.isValid}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {expirationDayOptions.map((days) => (
                      <SelectItem key={days} value={days.toString()}>
                        {days} Days
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FieldError errors={field.state.meta.errors} />
              </Field>
            )}
          </form.Field>

          <form.Field name="name">
            {(field) => (
              <Field data-invalid={!field.state.meta.isValid}>
                <FieldLabel htmlFor={field.name}>Name your key</FieldLabel>
                <Input
                  id={field.name}
                  aria-invalid={!field.state.meta.isValid}
                  value={field.state.value ?? ''}
                  onChange={(event) => field.handleChange(event.target.value)}
                  placeholder="Type your API key name here..."
                />
                <FieldError errors={field.state.meta.errors} />
              </Field>
            )}
          </form.Field>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit">Create API Key</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
