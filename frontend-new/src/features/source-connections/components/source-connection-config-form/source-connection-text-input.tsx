import * as React from 'react';
import { FormField } from '@/shared/config-fields';
import { Input } from '@/shared/ui/input';

export function SourceConnectionTextInput({
  description,
  errors,
  id,
  onBlur,
  onChange,
  required,
  title,
  type = 'text',
  value,
}: {
  description?: string;
  errors?: Array<{ message?: string } | undefined>;
  id: string;
  onBlur?: React.FocusEventHandler<HTMLInputElement>;
  onChange: (value: string) => void;
  required?: boolean;
  title: string;
  type?: React.HTMLInputTypeAttribute;
  value: string;
}) {
  const hasErrors = Boolean(errors?.length);

  return (
    <FormField
      description={description}
      errors={errors}
      name={id}
      required={required}
      title={title}
    >
      <Input
        aria-invalid={hasErrors}
        id={id}
        onBlur={onBlur}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
        placeholder={`Type ${title} here...`}
      />
    </FormField>
  );
}
