import type {
  ConfigField,
  DirectAuthentication,
  Source,
  SourceConnectionCreate,
} from '@/shared/api';
import type {
  SourceConnectionAuthMethod,
  SourceConnectionFormErrors,
  SourceConnectionFormValues,
} from './types';

const SUPPORTED_AUTH_METHODS: Array<SourceConnectionAuthMethod> = [
  'direct',
  'oauth_browser',
  'oauth_token',
  'auth_provider',
];

export function normalizeAuthMethod(
  authMethod: string | null | undefined,
): SourceConnectionAuthMethod | null {
  if (authMethod === 'oauth_byoc') {
    return 'oauth_browser';
  }

  return SUPPORTED_AUTH_METHODS.includes(
    authMethod as SourceConnectionAuthMethod,
  )
    ? (authMethod as SourceConnectionAuthMethod)
    : null;
}

export function getAvailableAuthMethods(source: Source) {
  const methods = (source.auth_methods ?? [])
    .map((method) => normalizeAuthMethod(method))
    .filter((method): method is SourceConnectionAuthMethod => method != null);

  return Array.from(new Set(methods));
}

export function getDefaultAuthMethod(
  source: Source,
): SourceConnectionAuthMethod {
  const methods = getAvailableAuthMethods(source);

  return methods[0] ?? 'direct';
}

export function getAuthMethodLabel(method: SourceConnectionAuthMethod) {
  switch (method) {
    case 'direct':
      return 'Direct';
    case 'oauth_browser':
      return 'OAuth Browser';
    case 'oauth_token':
      return 'OAuth Token';
    case 'auth_provider':
      return 'Auth Provider';
  }
}

export function deriveConnectionDescription({
  collectionName,
  sourceName,
}: {
  collectionName: string;
  sourceName: string;
}) {
  return `${sourceName} connection for ${collectionName}`;
}

export function getSyncImmediately({
  authMethod,
  source,
}: {
  authMethod: SourceConnectionAuthMethod;
  source: Source;
}) {
  if (source.supports_browse_tree) {
    return false;
  }

  return authMethod !== 'oauth_browser';
}

export function trimFormString(value: string) {
  const trimmedValue = value.trim();

  return trimmedValue.length > 0 ? trimmedValue : undefined;
}

export function buildDirectAuthentication(
  credentials: Record<string, unknown>,
): DirectAuthentication {
  return {
    credentials: trimEmptyValues(credentials),
  };
}

export function buildSourceConnectionPayload({
  authMethod,
  collectionName,
  readableCollectionId,
  source,
  values,
}: {
  authMethod: SourceConnectionAuthMethod;
  collectionName: string;
  readableCollectionId: string;
  source: Source;
  values: SourceConnectionFormValues;
}): SourceConnectionCreate {
  const syncImmediately = getSyncImmediately({ authMethod, source });

  return {
    authentication:
      authMethod === 'direct'
        ? buildDirectAuthentication(values.authentication.credentials ?? {})
        : null,
    config: trimEmptyValues(values.config),
    description: deriveConnectionDescription({
      collectionName,
      sourceName: source.name,
    }),
    name: trimFormString(values.name),
    readable_collection_id: readableCollectionId,
    short_name: source.short_name,
    sync_immediately: syncImmediately,
  };
}

export function trimEmptyValues(values: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(values).flatMap(([key, value]) => {
      if (value === null || value === undefined) {
        return [];
      }

      if (typeof value === 'string') {
        const trimmedValue = value.trim();
        return trimmedValue.length > 0 ? [[key, trimmedValue]] : [];
      }

      if (Array.isArray(value)) {
        const nextValue = value
          .map((item) => (typeof item === 'string' ? item.trim() : item))
          .filter((item) => item !== '' && item != null);

        return nextValue.length > 0 ? [[key, nextValue]] : [];
      }

      return [[key, value]];
    }),
  );
}

export function getInitialConfigValues(fields: Array<ConfigField>) {
  return Object.fromEntries(
    fields.map((field) => [field.name, getInitialFieldValue(field)]),
  );
}

export function getInitialDirectAuthenticationValues(
  fields: Array<ConfigField>,
) {
  return Object.fromEntries(
    fields.map((field) => [field.name, getInitialFieldValue(field)]),
  );
}

function getInitialFieldValue(field: ConfigField) {
  if (isBooleanField(field)) {
    return false;
  }

  if (isArrayField(field)) {
    return [];
  }

  return '';
}

export function parseFieldValue(
  field: ConfigField,
  rawValue: string | boolean,
) {
  if (typeof rawValue === 'boolean') {
    return rawValue;
  }

  if (isArrayField(field)) {
    return rawValue
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  if (isNumericField(field)) {
    const trimmedValue = rawValue.trim();
    return trimmedValue.length === 0 ? '' : Number(trimmedValue);
  }

  return rawValue;
}

export function formatFieldValue(field: ConfigField, value: unknown) {
  if (isBooleanField(field)) {
    return Boolean(value);
  }

  if (Array.isArray(value)) {
    return value.join('\n');
  }

  if (typeof value === 'number') {
    return String(value);
  }

  return typeof value === 'string' ? value : '';
}

export function validateSourceConnectionForm({
  authMethod,
  configFields,
  source,
  values,
}: {
  authMethod: SourceConnectionAuthMethod;
  configFields: Array<ConfigField>;
  source: Source;
  values: SourceConnectionFormValues;
}): SourceConnectionFormErrors {
  const errors: SourceConnectionFormErrors = {
    authentication: {},
    config: {},
  };

  for (const field of configFields) {
    const error = validateFieldValue(field, values.config[field.name]);
    if (error) {
      errors.config[field.name] = error;
    }
  }

  if (authMethod === 'direct') {
    const authFields = source.auth_fields?.fields ?? [];
    const credentials = values.authentication.credentials ?? {};

    for (const field of authFields) {
      const error = validateFieldValue(field, credentials[field.name]);
      if (error) {
        errors.authentication[field.name] = error;
      }
    }
  }

  return errors;
}

function validateFieldValue(field: ConfigField, value: unknown) {
  if (!field.required) {
    return undefined;
  }

  if (isBooleanField(field)) {
    return undefined;
  }

  if (Array.isArray(value)) {
    return value.length > 0 ? undefined : `${field.title} is required.`;
  }

  if (typeof value === 'number') {
    return Number.isNaN(value) ? `${field.title} is required.` : undefined;
  }

  if (typeof value === 'string') {
    return value.trim().length > 0 ? undefined : `${field.title} is required.`;
  }

  return value == null ? `${field.title} is required.` : undefined;
}

export function hasSourceConnectionFormErrors(
  errors: SourceConnectionFormErrors,
) {
  return (
    Object.keys(errors.config).length > 0 ||
    Object.keys(errors.authentication).length > 0 ||
    Boolean(errors.form)
  );
}

function isBooleanField(field: ConfigField) {
  return field.type === 'boolean' || field.type === 'bool';
}

function isArrayField(field: ConfigField) {
  return field.type === 'array' || field.items_type != null;
}

function isNumericField(field: ConfigField) {
  return ['float', 'int', 'integer', 'number'].includes(field.type);
}
