import { SourceFields } from './source-fields';
import type { SourceConnectionAuthSectionProps } from '../../types';

export function SourceConnectionDirectForm({
  authFields,
  errors,
  onChange,
  values,
}: SourceConnectionAuthSectionProps) {
  return (
    <SourceFields
      errors={errors}
      fields={authFields}
      onChange={onChange}
      values={values}
    />
  );
}
