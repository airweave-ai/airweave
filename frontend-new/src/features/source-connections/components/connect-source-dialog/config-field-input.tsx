import * as React from 'react';
import {
  Field,
  FieldContent,
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
  description?: string;
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
      <Field key={name} data-invalid={hasErrors} orientation="responsive">
        <FieldLabel htmlFor={name}>
          {title}
          {required ? <span className="text-destructive">*</span> : null}
        </FieldLabel>
        <Switch
          checked={value}
          id={name}
          onCheckedChange={(checked) => onChange(checked)}
          onBlur={onBlur}
          aria-invalid={hasErrors}
        />
        {description ? (
          <FieldDescription>{description}</FieldDescription>
        ) : null}
        <FieldError errors={errors} />
      </Field>
    );
  }

  if (fieldType === 'string') {
    return (
      <Field key={name} data-invalid={hasErrors}>
        <FieldLabel htmlFor={name}>
          {title}
          {required ? <RequiredMark /> : null}
        </FieldLabel>
        <Input
          id={name}
          type={'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          aria-invalid={hasErrors}
        />
        {description ? (
          <FieldDescription>{description}</FieldDescription>
        ) : null}
        <FieldError errors={errors} />
      </Field>
    );
  }

  if (fieldType === 'number') {
    return (
      <Field key={name} data-invalid={hasErrors}>
        <FieldLabel htmlFor={name}>
          {title}
          {required ? <RequiredMark /> : null}
        </FieldLabel>
        <Input
          id={name}
          type="number"
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.valueAsNumber)}
          onBlur={onBlur}
          aria-invalid={hasErrors}
        />
        {description ? (
          <FieldDescription>{description}</FieldDescription>
        ) : null}
        <FieldError errors={errors} />
      </Field>
    );
  }

  return (
    <Field key={name} data-invalid={hasErrors}>
      <FieldLabel htmlFor={name}>
        {title}
        {required ? <RequiredMark /> : null}
      </FieldLabel>
      <Input
        id={name}
        value={value}
        onChange={(e) => {
          const nextValue = e.target.value
            .split(',')
            .map((chunk) => chunk.trim());
          return onChange(nextValue);
        }}
        onBlur={onBlur}
        aria-invalid={hasErrors}
      />
      <FieldContent>
        {description ? (
          <FieldDescription>{description}</FieldDescription>
        ) : null}
        <FieldDescription>
          Separate values with commas or new lines.
        </FieldDescription>
      </FieldContent>
      <FieldError errors={errors} />
    </Field>
  );
}

function RequiredMark() {
  return <span className="-ml-1.5 text-destructive">*</span>;
}
