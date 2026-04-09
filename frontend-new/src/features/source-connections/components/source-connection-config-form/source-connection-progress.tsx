import { getAuthMethodForVariant } from './source-connection-form-hook';
import type {
  SourceConnectionAuthMethod,
  SourceConnectionAuthVariant,
} from './source-connection-form-hook';

export function SourceConnectionProgress({
  authVariant,
}: {
  authVariant: SourceConnectionAuthVariant;
}) {
  const authMethod = getAuthMethodForVariant(authVariant);
  const { step, numberOfSteps, label } = authMethodStepLabels[authMethod];

  return (
    <span className="font-mono text-sm text-foreground/60">
      Step {step}{' '}
      <span className="text-foreground/40">
        of {numberOfSteps}: {label}
      </span>
    </span>
  );
}

type Progress = {
  step: number;
  numberOfSteps: number;
  label: string;
};

const authMethodStepLabels: Record<SourceConnectionAuthMethod, Progress> = {
  direct: {
    step: 2,
    numberOfSteps: 2,
    label: 'Enter Token',
  },
  oauth_browser: {
    step: 1,
    numberOfSteps: 2,
    label: 'Configure',
  },
  oauth_token: {
    step: 2,
    numberOfSteps: 2,
    label: 'Enter Token',
  },
  auth_provider: {
    step: 2,
    numberOfSteps: 2,
    label: 'Configure',
  },
};
