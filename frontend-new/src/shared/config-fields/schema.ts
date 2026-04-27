import * as z from 'zod';
import type { ConfigField } from '@/shared/api';
import {
  optionalTrimmedStringSchema,
  trimmedStringSchema,
} from '@/shared/forms/schema';

export type ConfigFieldValue =
  | string
  | number
  | boolean
  | Array<string>
  | undefined;

const SUPPORTED_CONFIG_FIELD_TYPES = [
  'string',
  'number',
  'boolean',
  'array',
] as const;

type SupportedConfigFieldType = (typeof SUPPORTED_CONFIG_FIELD_TYPES)[number];

export function isSupportedConfigFieldType(
  fieldType: string,
): fieldType is SupportedConfigFieldType {
  return SUPPORTED_CONFIG_FIELD_TYPES.includes(
    fieldType as SupportedConfigFieldType,
  );
}

export function getDynamicFieldsSchema(fields: Array<ConfigField>) {
  const schema: Record<string, z.ZodType<ConfigFieldValue>> = {};

  for (const field of fields) {
    schema[field.name] = getDynamicFieldSchema(field);
  }

  return z.object(schema);
}

export function getDefaultConfigFieldsValues(
  configFields: Array<ConfigField> | undefined,
) {
  if (!configFields) {
    return {};
  }

  return Object.fromEntries(
    configFields
      .filter((field) => field.required)
      .map((field) => {
        return [field.name, getDefaultValueForConfigFieldType(field.type)];
      }),
  );
}

export function getDefaultValueForConfigFieldType(configFieldType: string) {
  const supportedConfigFieldType = isSupportedConfigFieldType(configFieldType)
    ? configFieldType
    : 'string';

  switch (supportedConfigFieldType) {
    case 'string':
      return '';
    case 'number':
      return 0;
    case 'boolean':
      return false;
    case 'array':
      return [] as Array<string>;
    default:
      supportedConfigFieldType satisfies never;
      throw new Error(`Unsupported field.type ${supportedConfigFieldType}`);
  }
}

function getDynamicFieldSchema(field: ConfigField) {
  const fieldType = isSupportedConfigFieldType(field.type)
    ? field.type
    : 'string';

  switch (fieldType) {
    case 'string':
      return field.required
        ? trimmedStringSchema.min(1, `${field.title} is required`)
        : optionalTrimmedStringSchema;
    case 'boolean':
      return field.required
        ? z.boolean(`${field.title} is required`)
        : z.boolean().optional();
    case 'number':
      return field.required
        ? z.number(`${field.title} is required`)
        : z.number().optional();
    case 'array': {
      const itemSchema = trimmedStringSchema;

      return field.required
        ? z.array(itemSchema).min(1, `${field.title} is required`)
        : z.array(itemSchema).optional();
    }
    default:
      fieldType satisfies never;
      throw new Error(`Unsupported field.type ${fieldType}`);
  }
}
