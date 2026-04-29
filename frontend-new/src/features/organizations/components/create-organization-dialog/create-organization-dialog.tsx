import * as React from 'react';
import { useCreateOrganizationMutation } from '../../api';
import { OrganizationNameStep } from './organization-name-step';
import { OrganizationSizeStep } from './organization-size-step';
import type { CreateOrganizationStep } from './steps';
import type { Organization } from '@/shared/api';
import type { OrganizationNameFormOutput } from './organization-name-step';
import type { OrganizationSizeFormOutput } from './organization-size-step';
import { FlowDialog } from '@/shared/components/flow-dialog';

type CreateOrganizationStepValues = Partial<{
  'organization-name': OrganizationNameFormOutput;
  'organization-size': OrganizationSizeFormOutput;
}>;

interface CreateOrganizationDialogProps {
  onCreated?: (organization: Organization) => void | Promise<void>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}

function CreateOrganizationDialog({
  onCreated,
  onOpenChange,
  open,
}: CreateOrganizationDialogProps) {
  const [step, setStep] =
    React.useState<CreateOrganizationStep>('organization-name');
  const [stepValues, setStepValues] =
    React.useState<CreateOrganizationStepValues>({});
  const createOrganizationMutation = useCreateOrganizationMutation();
  const isPending = createOrganizationMutation.isPending;

  const reset = React.useCallback(() => {
    setStep('organization-name');
    setStepValues({});
    createOrganizationMutation.reset();
  }, [createOrganizationMutation]);

  const close = React.useCallback(() => {
    onOpenChange(false);
    reset();
  }, [onOpenChange, reset]);

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && isPending) {
        return;
      }

      onOpenChange(nextOpen);

      if (!nextOpen) {
        reset();
      }
    },
    [isPending, onOpenChange, reset],
  );

  const createOrganization = React.useCallback(
    async (organizationSizeOutput: OrganizationSizeFormOutput) => {
      const nextStepValues = {
        ...stepValues,
        'organization-size': organizationSizeOutput,
      } satisfies CreateOrganizationStepValues;
      const organizationNameOutput = nextStepValues['organization-name'];

      if (!organizationNameOutput) {
        setStep('organization-name');
        return;
      }

      setStepValues(nextStepValues);

      const organization = await createOrganizationMutation.mutateAsync({
        body: {
          name: organizationNameOutput.organizationName,
          description: `Organization with ${organizationSizeOutput.organizationSize} people`,
          // TODO: Add invite metadata here once onboarding invite behavior and plan limits are decided.
          org_metadata: {
            onboarding: {
              completedAt: new Date().toISOString(),
              organizationSize: organizationSizeOutput.organizationSize,
            },
          },
        },
      });

      await onCreated?.(organization);
      close();
    },
    [close, createOrganizationMutation, onCreated, stepValues],
  );

  return (
    <FlowDialog open={open} onOpenChange={handleOpenChange}>
      {step === 'organization-name' ? (
        <OrganizationNameStep
          defaultValue={stepValues['organization-name']}
          isPending={isPending}
          onCancel={close}
          onSubmit={(organizationNameOutput) => {
            setStepValues((currentStepValues) => ({
              ...currentStepValues,
              'organization-name': organizationNameOutput,
            }));
            setStep('organization-size');
          }}
        />
      ) : (
        <OrganizationSizeStep
          defaultValue={stepValues['organization-size']}
          isPending={isPending}
          onCancel={close}
          onSubmit={createOrganization}
        />
      )}
    </FlowDialog>
  );
}

export { CreateOrganizationDialog };
