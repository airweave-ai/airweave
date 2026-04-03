import { formatFieldValue, parseFieldValue } from '../utils';
import type { SourceFieldGroupProps } from '../types';
import type { ConfigField } from '@/shared/api';
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldTitle,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { Switch } from '@/shared/ui/switch';
import { Textarea } from '@/shared/ui/textarea';

export function SourceFields({
  errors = {},
  fields,
  onChange,
  values,
}: SourceFieldGroupProps) {
  if (fields.length === 0) {
    return null;
  }

  return (
    <FieldGroup>
      {fields.map((field) => {
        const error = errors[field.name];
        const fieldId = `source-field-${field.name}`;
        const value = values[field.name];

        if (isBooleanField(field)) {
          return (
            <Field
              key={field.name}
              orientation="responsive"
              data-invalid={Boolean(error)}
            >
              <FieldContent>
                <FieldTitle>
                  {field.title}
                  {field.required ? (
                    <span className="text-destructive">*</span>
                  ) : null}
                </FieldTitle>
                {field.description ? (
                  <FieldDescription>{field.description}</FieldDescription>
                ) : null}
                <FieldError>{error}</FieldError>
              </FieldContent>

              <Switch
                aria-invalid={Boolean(error)}
                checked={Boolean(value)}
                id={fieldId}
                onCheckedChange={(checked) => onChange(field.name, checked)}
              />
            </Field>
          );
        }

        return (
          <Field key={field.name} data-invalid={Boolean(error)}>
            <FieldContent>
              <FieldTitle>
                {field.title}
                {field.required ? (
                  <span className="text-destructive">*</span>
                ) : null}
              </FieldTitle>
              {field.description ? (
                <FieldDescription>{field.description}</FieldDescription>
              ) : null}
              {isArrayField(field) ? (
                <FieldDescription>
                  Separate values with commas or new lines.
                </FieldDescription>
              ) : null}
            </FieldContent>

            {isArrayField(field) ? (
              <Textarea
                aria-invalid={Boolean(error)}
                id={fieldId}
                value={getTextFieldValue(field, value)}
                onChange={(event) =>
                  onChange(
                    field.name,
                    parseFieldValue(field, event.target.value),
                  )
                }
              />
            ) : (
              <Input
                aria-invalid={Boolean(error)}
                id={fieldId}
                inputMode={isNumericField(field) ? 'decimal' : undefined}
                type={field.is_secret ? 'password' : 'text'}
                value={getTextFieldValue(field, value)}
                onChange={(event) =>
                  onChange(
                    field.name,
                    parseFieldValue(field, event.target.value),
                  )
                }
              />
            )}

            <FieldError>{error}</FieldError>
          </Field>
        );
      })}
    </FieldGroup>
  );
}

function isArrayField(field: ConfigField) {
  return field.type === 'array' || field.items_type != null;
}

function isBooleanField(field: ConfigField) {
  return field.type === 'boolean' || field.type === 'bool';
}

function isNumericField(field: ConfigField) {
  return ['float', 'int', 'integer', 'number'].includes(field.type);
}

function getTextFieldValue(field: ConfigField, value: unknown) {
  const fieldValue = formatFieldValue(field, value);

  return typeof fieldValue === 'string' ? fieldValue : '';
}
