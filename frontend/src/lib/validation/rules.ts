/**
 * Validation rules for the collection creation flow
 */

import type { FieldValidation, ValidationResult } from './types';

/**
 * Collection name validation
 * Requirements: 4-64 characters
 */
export const collectionNameValidation: FieldValidation<string> = {
  field: 'collectionName',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Too short
    if (trimmed.length < 4) {
      return {
        isValid: false,
        hint: `${4 - trimmed.length} more character${4 - trimmed.length > 1 ? 's' : ''} needed`,
        severity: 'info'
      };
    }

    // Too long
    if (trimmed.length > 64) {
      return {
        isValid: false,
        hint: 'Maximum 64 characters',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Source connection name validation
 * Requirements: 4-42 characters
 */
export const sourceConnectionNameValidation: FieldValidation<string> = {
  field: 'sourceConnectionName',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    if (trimmed.length < 4) {
      return {
        isValid: false,
        hint: `${4 - trimmed.length} more character${4 - trimmed.length > 1 ? 's' : ''} needed`,
        severity: 'info'
      };
    }

    if (trimmed.length > 42) {
      return {
        isValid: false,
        hint: 'Maximum 42 characters',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * API key validation
 */
export const apiKeyValidation: FieldValidation<string> = {
  field: 'api_key',
  debounceMs: 0,
  showOn: 'blur',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    // Check for placeholder values
    const placeholders = ['your-api-key', 'xxx', 'api-key-here', 'paste-here'];
    if (placeholders.some(p => value.toLowerCase().includes(p))) {
      return {
        isValid: false,
        hint: 'Enter your actual API key',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * URL validation
 */
export const urlValidation: FieldValidation<string> = {
  field: 'url',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    try {
      new URL(value);
      return { isValid: true, severity: 'info' };
    } catch {
      return {
        isValid: false,
        hint: 'Invalid URL format',
        severity: 'info'
      };
    }
  }
};

/**
 * Email validation
 */
export const emailValidation: FieldValidation<string> = {
  field: 'email',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(value)) {
      return {
        isValid: false,
        hint: 'Invalid email format',
        severity: 'info'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * OAuth Client ID validation
 */
export const clientIdValidation: FieldValidation<string> = {
  field: 'clientId',
  showOn: 'blur',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    if (value.toLowerCase().includes('your-client-id')) {
      return {
        isValid: false,
        hint: 'Enter your actual Client ID',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * OAuth Client Secret validation
 */
export const clientSecretValidation: FieldValidation<string> = {
  field: 'clientSecret',
  showOn: 'blur',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    if (value.toLowerCase().includes('your-secret')) {
      return {
        isValid: false,
        hint: 'Enter your actual Client Secret',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Auth provider config ID validation
 * Requirements: Non-empty, alphanumeric with underscores
 */
export const authConfigIdValidation: FieldValidation<string> = {
  field: 'authConfigId',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Check for valid characters (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: 'Only letters, numbers, underscores, and hyphens allowed',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Account ID validation
 * Requirements: Non-empty, alphanumeric with underscores
 */
export const accountIdValidation: FieldValidation<string> = {
  field: 'accountId',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Check for valid characters (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: 'Only letters, numbers, underscores, and hyphens allowed',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Workflow ID validation (for Pipedream)
 * Requirements: Non-empty, starts with p_
 */
export const workflowIdValidation: FieldValidation<string> = {
  field: 'workflowId',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Check if starts with p_
    if (!trimmed.startsWith('p_')) {
      return {
        isValid: false,
        hint: 'Workflow ID should start with "p_"',
        severity: 'info'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Project ID validation for Pipedream
 * Requirements: Non-empty, starts with proj_
 */
export const projectIdValidation: FieldValidation<string> = {
  field: 'projectId',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Check if starts with proj_
    if (!trimmed.startsWith('proj_')) {
      return {
        isValid: false,
        hint: 'Project ID should start with "proj_"',
        severity: 'info'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Environment validation for Pipedream
 * Requirements: Either 'production' or 'development'
 */
export const environmentValidation: FieldValidation<string> = {
  field: 'environment',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim().toLowerCase();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    if (trimmed !== 'production' && trimmed !== 'development') {
      return {
        isValid: false,
        hint: 'Environment must be either "production" or "development"',
        severity: 'info'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * External User ID validation for Pipedream
 * Requirements: Optional field, alphanumeric with underscores/hyphens
 */
export const externalUserIdValidation: FieldValidation<string> = {
  field: 'externalUserId',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    // Optional field - empty is valid
    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Check for valid characters (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: 'External User ID can only contain letters, numbers, underscores, and hyphens',
        severity: 'info'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Redirect URL validation
 */
export const redirectUrlValidation: FieldValidation<string> = {
  field: 'redirectUrl',
  debounceMs: 300,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    const trimmed = value.trim();

    // Check if URL starts with protocol
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      return {
        isValid: false,
        hint: 'URL must start with http:// or https://',
        severity: 'warning'
      };
    }

    try {
      const url = new URL(trimmed);

      // Check for valid protocol
      if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        return {
          isValid: false,
          hint: 'Must use http:// or https:// protocol',
          severity: 'warning'
        };
      }

      // Check for valid hostname
      if (!url.hostname || url.hostname.length === 0) {
        return {
          isValid: false,
          hint: 'URL must include a valid hostname',
          severity: 'warning'
        };
      }

      // Check for localhost or valid domain
      const isValidHostname =
        url.hostname === 'localhost' ||
        url.hostname.includes('.') ||
        /^[a-zA-Z0-9-]+$/.test(url.hostname);

      if (!isValidHostname) {
        return {
          isValid: false,
          hint: 'Invalid hostname format',
          severity: 'warning'
        };
      }

      // Suggest HTTPS for production URLs
      if (url.protocol === 'http:' && !url.hostname.includes('localhost')) {
        return {
          isValid: true,
          hint: 'Consider using https:// for production URLs',
          severity: 'info'
        };
      }

      return { isValid: true, severity: 'info' };
    } catch {
      return {
        isValid: false,
        hint: 'Invalid URL format',
        severity: 'warning'
      };
    }
  }
};

/**
 * Get validation for a specific auth field type
 */
export function getAuthFieldValidation(fieldType: string): FieldValidation<string> | null {
  switch (fieldType) {
    case 'api_key':
    case 'token':
    case 'access_token':
    case 'personal_access_token':
      return apiKeyValidation;
    case 'url':
    case 'endpoint':
    case 'base_url':
    case 'cluster_url':
      // Note: 'host' is NOT included - database hosts don't need http:// prefix
      return urlValidation;
    case 'email':
    case 'username':
      return emailValidation;
    case 'client_id':
      return clientIdValidation;
    case 'client_secret':
      return clientSecretValidation;
    case 'auth_config_id':
      return authConfigIdValidation;
    case 'account_id':
      return accountIdValidation;
    case 'workflow_id':
      return workflowIdValidation;
    case 'project_id':
      return projectIdValidation;
    case 'environment':
      return environmentValidation;
    case 'external_user_id':
      return externalUserIdValidation;
    default:
      return null;
  }
}
