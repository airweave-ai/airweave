import * as React from 'react';
import { steps } from './steps';
import type { CreateOrganizationStep } from './steps';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogContent,
  FlowDialogFooter,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

interface CreateOrganizationDialogLayoutProps {
  description: React.ReactNode;
  footer: React.ReactNode;
  onClose: () => void;
  step: CreateOrganizationStep;
  title: React.ReactNode;
}

function getStepIndex(step: CreateOrganizationStep) {
  return steps.indexOf(step) + 1;
}

function CreateOrganizationDialogLayout({
  children,
  description,
  footer,
  onClose,
  step,
  title,
}: React.PropsWithChildren<CreateOrganizationDialogLayoutProps>) {
  return (
    <FlowDialogContent size="sm">
      <FlowDialogHeader align="center" onClose={onClose}>
        <p className="text-sm font-medium text-muted-foreground">
          <span className="text-foreground">Step {getStepIndex(step)}</span> of{' '}
          {steps.length}
        </p>
      </FlowDialogHeader>

      <div className="space-y-1 px-6 py-4 text-center">
        <DialogTitle className="text-xl leading-7 font-semibold">
          {title}
        </DialogTitle>
        <DialogDescription className="font-mono">
          {description}
        </DialogDescription>
      </div>

      <FlowDialogMain className="overflow-y-auto px-6 py-6">
        {children}
      </FlowDialogMain>

      <FlowDialogFooter>{footer}</FlowDialogFooter>
    </FlowDialogContent>
  );
}

export { CreateOrganizationDialogLayout };
