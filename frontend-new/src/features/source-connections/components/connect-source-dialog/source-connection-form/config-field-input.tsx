import * as React from 'react';
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { Switch } from '@/shared/ui/switch';

type Errors = Array<{ message?: string } | undefined>;

type CommonConfigFieldInputProps = {
  name: string;
  title: string;
  required?: boolean;
  description?: React.ReactNode;
  errors?: Errors;
  onBlur?: React.FocusEventHandler;
};

type StringConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'string';
  value: string;
  onChange: (value: string) => void;
};
type BooleanConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'boolean';
  value: boolean;
  onChange: (value: boolean) => void;
};
type NumberConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'number';
  value: number;
  onChange: (value: number) => void;
};
type ArrayConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'array';
  value: Array<string>;
  onChange: (value: Array<string>) => void;
};
type ConfigFieldInputProps =
  | StringConfigFieldInputProps
  | BooleanConfigFieldInputProps
  | NumberConfigFieldInputProps
  | ArrayConfigFieldInputProps;

export function ConfigFieldInput({
  fieldType,
  name,
  title,
  required,
  description,
  value,
  onChange,
  onBlur,
  errors,
}: ConfigFieldInputProps) {
  const hasErrors = Boolean(errors?.length);

  if (fieldType === 'boolean') {
    return (
      <FormField
        description={description}
        errors={errors}
        name={name}
        required={required}
        title={title}
      >
        <Switch
          aria-invalid={hasErrors}
          checked={value}
          id={name}
          onBlur={onBlur}
          onCheckedChange={(checked) => onChange(checked)}
        />
      </FormField>
    );
  }

  if (fieldType === 'string') {
    return (
      <FormField
        description={description}
        errors={errors}
        name={name}
        required={required}
        title={title}
      >
        <Input
          aria-invalid={hasErrors}
          id={name}
          onBlur={onBlur}
          onChange={(e) => onChange(e.target.value)}
          type="text"
          value={value}
        />
      </FormField>
    );
  }

  if (fieldType === 'number') {
    return (
      <FormField
        description={description}
        errors={errors}
        name={name}
        required={required}
        title={title}
      >
        <Input
          aria-invalid={hasErrors}
          id={name}
          inputMode="decimal"
          onBlur={onBlur}
          onChange={(e) => onChange(e.target.valueAsNumber)}
          type="number"
          value={value}
        />
      </FormField>
    );
  }

  return (
    <FormField
      description={
        <>
          {description ? <FieldDescription>{description}</FieldDescription> : null}
          <FieldDescription>
            Separate values with commas or new lines.
          </FieldDescription>
        </>
      }
      errors={errors}
      name={name}
      required={required}
      title={title}
    >
      <Input
        aria-invalid={hasErrors}
        id={name}
        onBlur={onBlur}
        onChange={(e) => {
          const nextValue = e.target.value.split(',').map((chunk) => chunk.trim());
          return onChange(nextValue);
        }}
        value={value}
      />
    </FormField>
  );
}

export function FormField({
  name,
  title,
  errors,
  required,
  description,
  children,
}: React.PropsWithChildren<Omit<CommonConfigFieldInputProps, 'onBlur'>>) {
  const hasErrors = Boolean(errors?.length);
  return (
    <Field data-invalid={hasErrors}>
      <FieldLabel htmlFor={name}>
        {title}
        {required ? <RequiredMark /> : null}
      </FieldLabel>
      {description
        ? typeof description === 'string'
          ? <FieldDescription>{description}</FieldDescription>
          : description
        : null}
      {children}
      <FieldError errors={errors} />
    </Field>
  );
}

function RequiredMark() {
  return <span className="-ml-1.5 text-destructive">*</span>;
}
