import * as React from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useCreateCollectionMutation } from '../api';
import type { Collection } from '@/shared/api';
import { parseApiErrorWithDetail } from '@/shared/api';
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
  FlowDialog,
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogContent,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';
import { Input } from '@/shared/ui/input';
import { Separator } from '@/shared/ui/separator';
import { Spinner } from '@/shared/ui/spinner';

const collectionBenefits = [
  'Search only what you choose',
  'Keep synced data together',
  'Control collection access',
] as const;

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

interface CreateCollectionDialogProps {
  onClose: () => void;
  onCreated: (collection: Collection) => void;
}

export function CreateCollectionDialog({
  onClose,
  onCreated,
}: CreateCollectionDialogProps) {
  const createCollectionMutation = useCreateCollectionMutation();
  const [isOpen, setIsOpen] = React.useState(true);
  const [name, setName] = React.useState('');
  const [nameError, setNameError] = React.useState<string>();
  const [submitError, setSubmitError] = React.useState<string>();

  const isPending = createCollectionMutation.isPending;

  const handleClose = React.useCallback(() => {
    if (isPending) {
      return;
    }

    setIsOpen(false);
  }, [isPending]);

  const handleSubmit = React.useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      const trimmedName = name.trim();

      if (!trimmedName) {
        setNameError('Collection name is required.');
        setSubmitError(undefined);
        return;
      }

      setNameError(undefined);
      setSubmitError(undefined);

      try {
        const collection = await createCollectionMutation.mutateAsync({
          body: { name: trimmedName },
        });

        onCreated(collection);
      } catch (error) {
        setSubmitError(getSubmitErrorMessage(error));
      }
    },
    [createCollectionMutation, name, onCreated],
  );

  return (
    <FlowDialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <FlowDialogContent
        className="bg-background"
        onAnimationEnd={() => {
          if (!isOpen) {
            onClose();
          }
        }}
      >
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
          <FlowDialogAside className="flex flex-col xl:w-[27rem]">
            <form className="flex min-h-full flex-col" onSubmit={handleSubmit}>
              <FieldGroup>
                <Field>
                  <FieldContent>
                    <FieldTitle>Collection Name</FieldTitle>
                  </FieldContent>
                  <Input
                    autoFocus
                    value={name}
                    onChange={(event) => {
                      setName(event.target.value);
                      setNameError(undefined);
                      setSubmitError(undefined);
                    }}
                    placeholder="Type your collection name here..."
                    aria-invalid={Boolean(nameError)}
                  />
                  <FieldDescription>
                    Used in API and Connect session setup.
                    <br />
                    You can rename this later.
                  </FieldDescription>
                  <FieldError>{nameError}</FieldError>
                </Field>
              </FieldGroup>

              <div className="mt-auto space-y-4 pt-6">
                <FieldError>{submitError}</FieldError>

                <Button className="w-full" disabled={isPending} type="submit">
                  {isPending ? <Spinner className="size-4" /> : null}
                  Create & Continue
                </Button>

                <Button
                  className="w-full"
                  disabled={isPending}
                  type="button"
                  variant="ghost"
                  onClick={handleClose}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </FlowDialogAside>

          <FlowDialogMain className="space-y-8">
            <section className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <h2 className="text-lg font-semibold text-foreground">
                    What is a collection?
                  </h2>
                  <p className="max-w-3xl font-mono text-sm text-muted-foreground">
                    A collection is your agent&apos;s scoped knowledge space. It
                    groups selected sources and indexed entities, so queries run
                    only against the data you choose.
                  </p>
                </div>

                <Button asChild size="lg" variant="ghost">
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

              <Separator />

              <div className="grid gap-3 xl:grid-cols-3">
                {collectionBenefits.map((benefit) => (
                  <div
                    key={benefit}
                    className="flex items-center gap-3 rounded-xl px-1 py-1 text-sm text-foreground"
                  >
                    <span className="flex size-5 items-center justify-center rounded-sm border border-border bg-foreground/5">
                      <span className="size-1.5 rounded-full bg-foreground" />
                    </span>
                    <span className="font-mono">{benefit}</span>
                  </div>
                ))}
              </div>

              <Separator />
            </section>

            <section className="space-y-2">
              <h3 className="text-base font-semibold text-foreground">
                What happens next:
              </h3>

              <div>
                {nextSteps.map((step, index) => (
                  <React.Fragment key={step.title}>
                    <div className="space-y-2 py-3">
                      <div className="flex items-center gap-2">
                        <span className="flex size-6 items-center justify-center rounded-sm border border-border font-mono text-sm text-muted-foreground">
                          {index + 1}
                        </span>
                        <p className="text-sm font-extrabold text-foreground">
                          {step.title}
                        </p>
                      </div>
                      <p className="font-mono text-sm text-muted-foreground">
                        {step.description}
                      </p>
                    </div>
                    {index < nextSteps.length - 1 ? <Separator /> : null}
                  </React.Fragment>
                ))}
              </div>
            </section>

            <p className="pt-4 font-mono text-sm text-muted-foreground">
              You can rename this collection, add or remove sources, and pause
              sync at any time.
            </p>
          </FlowDialogMain>
        </FlowDialogBody>
      </FlowDialogContent>
    </FlowDialog>
  );
}

function getSubmitErrorMessage(error: unknown) {
  const parsedError = parseApiErrorWithDetail(error);

  if (parsedError?.detail) {
    return parsedError.detail;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return 'Could not create collection.';
}
