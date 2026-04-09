import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { ArrowUpRight } from 'lucide-react';
import * as z from 'zod';
import { IconArrowRight } from '@tabler/icons-react';
import { useCreateCollectionMutation } from '../api';
import type { Collection, CreateCollectionsPostError } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { Button } from '@/shared/ui/button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldTitle,
} from '@/shared/ui/field';
import {
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';
import { Input } from '@/shared/ui/input';
import { Separator } from '@/shared/ui/separator';
import { Spinner } from '@/shared/ui/spinner';

const nextSteps = [
  {
    description: 'Choose which apps to include in this collection.',
    title: 'Select sources',
  },
  {
    description: 'Authorize each source with OAuth or credentials.',
    title: 'Connect accounts',
  },
  {
    description: 'Airweave starts syncing entities for search.',
    title: 'Sync and index',
  },
  {
    description: 'Query this collection via API, SDK, Cursor, or Claude Code.',
    title: 'Query with your agent',
  },
] as const;

const createCollectionFormSchema = z.object({
  name: z.string().trim().min(1, 'Collection name is required.'),
});

const createCollectionNameSchema = createCollectionFormSchema.shape.name;

const defaultFormValues = {
  name: '',
};

interface CreateCollectionDialogScreenProps {
  onClose: () => void;
  onCreated: (collection: Collection) => void;
}

export function CreateCollectionDialogScreen({
  onClose,
  onCreated,
}: CreateCollectionDialogScreenProps) {
  const createCollectionMutation = useCreateCollectionMutation();

  const isPending = createCollectionMutation.isPending;
  const submitError = getSubmitErrorMessage(createCollectionMutation.error);

  const form = useForm({
    defaultValues: defaultFormValues,
    validators: {
      onSubmit: createCollectionFormSchema,
    },
    onSubmit: async ({ value }) => {
      const collection = await createCollectionMutation.mutateAsync({
        body: { name: value.name.trim() },
      });

      onCreated(collection);
    },
  });

  const handleClose = React.useCallback(() => {
    if (isPending) {
      return;
    }

    onClose();
  }, [isPending]);

  return (
    <>
      <FlowDialogHeader onClose={handleClose}>
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold text-foreground">
            Create Collection
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            Create a collection to organize sources and searchable context.
          </DialogDescription>
        </div>
      </FlowDialogHeader>

      <FlowDialogBody>
        <FlowDialogMain className="flex flex-col">
          <form
            className="flex min-h-full flex-col"
            onSubmit={(event) => {
              event.preventDefault();
              void form.handleSubmit();
            }}
          >
            <FieldGroup>
              <form.Field
                name="name"
                validators={{
                  onBlur: createCollectionNameSchema,
                }}
              >
                {(field) => (
                  <Field>
                    <FieldContent>
                      <FieldTitle>Collection Name</FieldTitle>
                    </FieldContent>
                    <Input
                      autoFocus
                      value={field.state.value}
                      onBlur={field.handleBlur}
                      onChange={(event) => {
                        if (createCollectionMutation.error) {
                          createCollectionMutation.reset();
                        }

                        field.handleChange(event.target.value);
                      }}
                      placeholder="Type your collection name here..."
                      aria-invalid={field.state.meta.errors.length > 0}
                    />
                    <FieldDescription>
                      Used in API and Connect session setup. You can rename this
                      later.
                    </FieldDescription>
                  </Field>
                )}
              </form.Field>
            </FieldGroup>

            <div className="mt-auto space-y-4 pt-6">
              <FieldError>{submitError}</FieldError>

              <div className="flex min-h-15 items-end justify-between gap-4">
                <Button
                  className="max-w-55 flex-1"
                  disabled={isPending}
                  size="lg"
                  type="button"
                  variant="ghost"
                  onClick={handleClose}
                >
                  Back
                </Button>
                <div className="max-w-130 flex-1 space-y-2">
                  <form.Subscribe
                    selector={(state) => state.fieldMeta.name?.errors}
                  >
                    {(nameErrors) => (
                      <FieldError className="text-center" errors={nameErrors} />
                    )}
                  </form.Subscribe>
                  <Button
                    size="lg"
                    className="w-full"
                    disabled={isPending}
                    type="submit"
                  >
                    Create & Continue
                    {isPending ? (
                      <Spinner className="size-4" />
                    ) : (
                      <IconArrowRight className="size-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </form>
        </FlowDialogMain>

        <FlowDialogAside className="flex min-h-full flex-col gap-4 p-4 xl:w-112">
          <section className="space-y-4">
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-foreground">
                  What is a collection?
                </h2>
                <Button asChild size="lg" variant="ghost" className="shrink-0">
                  <a
                    href="https://docs.airweave.ai/welcome"
                    rel="noreferrer"
                    target="_blank"
                  >
                    Documentation
                    <ArrowUpRight className="size-4" />
                  </a>
                </Button>
              </div>
              <p className="font-mono text-sm leading-5 text-muted-foreground">
                A collection is your agent&apos;s scoped knowledge space. It
                groups selected sources and indexed entities, so queries run
                only against the data you choose.
              </p>
            </div>

            <Separator />
          </section>

          <section className="space-y-2">
            <h3 className="text-base leading-none font-semibold text-foreground">
              What happens next:
            </h3>

            <div>
              {nextSteps.map((step, index) => (
                <React.Fragment key={step.title}>
                  <div className="space-y-2 py-3">
                    <div className="flex items-center gap-2">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-sm border text-sm font-medium text-muted-foreground">
                        {index + 1}
                      </span>
                      <p className="text-sm font-extrabold text-foreground">
                        {step.title}
                      </p>
                    </div>
                    <p className="font-mono text-sm leading-5 text-muted-foreground">
                      {step.description}
                    </p>
                  </div>
                  {index < nextSteps.length - 1 ? (
                    <Separator className="my-2" />
                  ) : null}
                </React.Fragment>
              ))}
            </div>
          </section>

          <p className="mt-auto pt-4 font-mono text-sm leading-5 text-muted-foreground">
            You can rename this collection, add/remove sources, and pause sync
            at any time.
          </p>
        </FlowDialogAside>
      </FlowDialogBody>
    </>
  );
}

function getSubmitErrorMessage(error: CreateCollectionsPostError | null) {
  return getApiErrorMessage(error, 'Could not create collection.');
}
