import * as React from 'react';
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldTitle,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { Switch } from '@/shared/ui/switch';

type Errors = Array<{ message?: string } | undefined>;

type CommonConfigFieldInputProps = {
  description?: React.ReactNode;
  disabled?: boolean;
  errors?: Errors;
  isSecret?: boolean;
  name: string;
  onBlur?: React.FocusEventHandler;
  placeholder?: string;
  required?: boolean;
  title: string;
};

type StringConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'string';
  onChange: (value: string) => void;
  value: string;
};

type BooleanConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'boolean';
  onChange: (value: boolean) => void;
  value: boolean;
};

type NumberConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'number';
  onChange: (value: number) => void;
  value: number;
};

type ArrayConfigFieldInputProps = CommonConfigFieldInputProps & {
  fieldType: 'array';
  onChange: (value: Array<string>) => void;
  value: Array<string>;
};

type ConfigFieldInputProps =
  | StringConfigFieldInputProps
  | BooleanConfigFieldInputProps
  | NumberConfigFieldInputProps
  | ArrayConfigFieldInputProps;

export function ConfigFieldInput({
  description,
  disabled,
  errors,
  fieldType,
  isSecret,
  name,
  onBlur,
  onChange,
  placeholder,
  required,
  title,
  value,
}: ConfigFieldInputProps) {
  const hasErrors = Boolean(errors?.length);

  if (fieldType === 'boolean') {
    return (
      <FieldLabel>
        <Field
          data-disabled={disabled}
          data-invalid={hasErrors}
          orientation="horizontal"
        >
          <FieldContent>
            <FieldTitle>{title}</FieldTitle>
            {description ? (
              <FieldDescription className="text-balance">
                {description}
              </FieldDescription>
            ) : null}
          </FieldContent>
          <Switch
            aria-invalid={hasErrors}
            checked={value}
            disabled={disabled}
            id={name}
            onBlur={onBlur}
            onCheckedChange={(checked) => onChange(checked)}
          />
        </Field>
      </FieldLabel>
    );
  }

  if (fieldType === 'string') {
    return (
      <FormField
        description={description}
        disabled={disabled}
        errors={errors}
        name={name}
        required={required}
        title={title}
      >
        <Input
          aria-invalid={hasErrors}
          disabled={disabled}
          id={name}
          onBlur={onBlur}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder ?? `Type ${title} here...`}
          type={isSecret ? 'password' : 'text'}
          value={value}
        />
      </FormField>
    );
  }

  if (fieldType === 'number') {
    return (
      <FormField
        description={description}
        disabled={disabled}
        errors={errors}
        name={name}
        required={required}
        title={title}
      >
        <Input
          aria-invalid={hasErrors}
          disabled={disabled}
          id={name}
          inputMode="decimal"
          onBlur={onBlur}
          onChange={(event) => onChange(event.target.valueAsNumber)}
          placeholder={placeholder}
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
          {description ? (
            <FieldDescription className="text-balance">
              {description}
            </FieldDescription>
          ) : null}
          <FieldDescription>
            Separate values with commas or new lines.
          </FieldDescription>
        </>
      }
      disabled={disabled}
      errors={errors}
      name={name}
      required={required}
      title={title}
    >
      <Input
        aria-invalid={hasErrors}
        disabled={disabled}
        id={name}
        onBlur={onBlur}
        onChange={(event) => {
          const nextValue = event.target.value
            .split(/[\n,]/)
            .map((chunk) => chunk.trim())
            .filter(Boolean);

          return onChange(nextValue);
        }}
        placeholder={placeholder ?? `Type ${title} here...`}
        value={value.join(', ')}
      />
    </FormField>
  );
}

export function FormField({
  children,
  description,
  disabled,
  errors,
  name,
  required,
  title,
}: React.PropsWithChildren<
  Omit<CommonConfigFieldInputProps, 'onBlur' | 'placeholder'>
>) {
  const hasErrors = Boolean(errors?.length);

  return (
    <Field data-disabled={disabled} data-invalid={hasErrors}>
      <FieldLabel htmlFor={name}>
        {title}
        {required ? <RequiredMark /> : null}
      </FieldLabel>
      {description ? (
        typeof description === 'string' ? (
          <FieldDescription className="text-balance">
            {description}
          </FieldDescription>
        ) : (
          description
        )
      ) : null}
      {children}
      <FieldError errors={errors} />
    </Field>
  );
}

function RequiredMark() {
  return <span className="-ml-1.5 text-destructive">*</span>;
}
