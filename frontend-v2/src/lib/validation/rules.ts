/**
 * Validation rules for the Airweave application
 * Ported from frontend/src/lib/validation/rules.ts
 */

import type { FieldValidation, ValidationResult } from "./types";

/**
 * Collection name validation
 * Requirements: 4-64 characters
 */
export const collectionNameValidation: FieldValidation<string> = {
  field: "collectionName",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Too short
    if (trimmed.length < 4) {
      return {
        isValid: false,
        hint: `${4 - trimmed.length} more character${4 - trimmed.length > 1 ? "s" : ""} needed`,
        severity: "info",
      };
    }

    // Too long
    if (trimmed.length > 64) {
      return {
        isValid: false,
        hint: "Maximum 64 characters",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Source connection name validation
 * Requirements: 4-42 characters
 */
export const sourceConnectionNameValidation: FieldValidation<string> = {
  field: "sourceConnectionName",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    if (trimmed.length < 4) {
      return {
        isValid: false,
        hint: `${4 - trimmed.length} more character${4 - trimmed.length > 1 ? "s" : ""} needed`,
        severity: "info",
      };
    }

    if (trimmed.length > 42) {
      return {
        isValid: false,
        hint: "Maximum 42 characters",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * API key validation
 */
export const apiKeyValidation: FieldValidation<string> = {
  field: "api_key",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: "info" };

    // Check for placeholder values
    const placeholders = ["your-api-key", "xxx", "api-key-here", "paste-here"];
    if (placeholders.some((p) => value.toLowerCase().includes(p))) {
      return {
        isValid: false,
        hint: "Enter your actual API key",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * URL validation
 */
export const urlValidation: FieldValidation<string> = {
  field: "url",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: "info" };

    try {
      new URL(value);
      return { isValid: true, severity: "info" };
    } catch {
      return {
        isValid: false,
        hint: "Invalid URL format",
        severity: "info",
      };
    }
  },
};

/**
 * Email validation
 */
export const emailValidation: FieldValidation<string> = {
  field: "email",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: "info" };

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(value)) {
      return {
        isValid: false,
        hint: "Invalid email format",
        severity: "info",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * OAuth Client ID validation
 */
export const clientIdValidation: FieldValidation<string> = {
  field: "clientId",
  showOn: "blur",
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: "info" };

    if (value.toLowerCase().includes("your-client-id")) {
      return {
        isValid: false,
        hint: "Enter your actual Client ID",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * OAuth Client Secret validation
 */
export const clientSecretValidation: FieldValidation<string> = {
  field: "clientSecret",
  showOn: "blur",
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: "info" };

    if (value.toLowerCase().includes("your-secret")) {
      return {
        isValid: false,
        hint: "Enter your actual Client Secret",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Auth provider config ID validation
 * Requirements: Non-empty, alphanumeric with underscores
 */
export const authConfigIdValidation: FieldValidation<string> = {
  field: "authConfigId",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check for valid characters (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: "Only letters, numbers, underscores, and hyphens allowed",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Account ID validation
 * Requirements: Non-empty, alphanumeric with underscores
 */
export const accountIdValidation: FieldValidation<string> = {
  field: "accountId",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check for valid characters (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: "Only letters, numbers, underscores, and hyphens allowed",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Workflow ID validation (for Pipedream)
 * Requirements: Non-empty, starts with p_
 */
export const workflowIdValidation: FieldValidation<string> = {
  field: "workflowId",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check if starts with p_
    if (!trimmed.startsWith("p_")) {
      return {
        isValid: false,
        hint: 'Workflow ID should start with "p_"',
        severity: "info",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Project ID validation for Pipedream
 * Requirements: Non-empty, starts with proj_
 */
export const projectIdValidation: FieldValidation<string> = {
  field: "projectId",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check if starts with proj_
    if (!trimmed.startsWith("proj_")) {
      return {
        isValid: false,
        hint: 'Project ID should start with "proj_"',
        severity: "info",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Environment validation for Pipedream
 * Requirements: Either 'production' or 'development'
 */
export const environmentValidation: FieldValidation<string> = {
  field: "environment",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim().toLowerCase();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    if (trimmed !== "production" && trimmed !== "development") {
      return {
        isValid: false,
        hint: 'Environment must be either "production" or "development"',
        severity: "info",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * External User ID validation for Pipedream
 * Requirements: Optional field, alphanumeric with underscores/hyphens
 */
export const externalUserIdValidation: FieldValidation<string> = {
  field: "externalUserId",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    // Optional field - empty is valid
    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check for valid characters (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: "External User ID can only contain letters, numbers, underscores, and hyphens",
        severity: "info",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Redirect URL validation
 */
export const redirectUrlValidation: FieldValidation<string> = {
  field: "redirectUrl",
  debounceMs: 300,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: "info" };

    const trimmed = value.trim();

    // Check if URL starts with protocol
    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
      return {
        isValid: false,
        hint: "URL must start with http:// or https://",
        severity: "warning",
      };
    }

    try {
      const url = new URL(trimmed);

      // Check for valid protocol
      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return {
          isValid: false,
          hint: "Must use http:// or https:// protocol",
          severity: "warning",
        };
      }

      // Check for valid hostname
      if (!url.hostname || url.hostname.length === 0) {
        return {
          isValid: false,
          hint: "URL must include a valid hostname",
          severity: "warning",
        };
      }

      // Check for localhost or valid domain
      const isValidHostname =
        url.hostname === "localhost" ||
        url.hostname.includes(".") ||
        /^[a-zA-Z0-9-]+$/.test(url.hostname);

      if (!isValidHostname) {
        return {
          isValid: false,
          hint: "Invalid hostname format",
          severity: "warning",
        };
      }

      // Suggest HTTPS for production URLs
      if (url.protocol === "http:" && !url.hostname.includes("localhost")) {
        return {
          isValid: true,
          hint: "Consider using https:// for production URLs",
          severity: "info",
        };
      }

      return { isValid: true, severity: "info" };
    } catch {
      return {
        isValid: false,
        hint: "Invalid URL format",
        severity: "warning",
      };
    }
  },
};

/**
 * Repository name validation (owner/repo format)
 */
export const repoNameValidation: FieldValidation<string> = {
  field: "repo_name",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Must contain a slash
    if (!trimmed.includes("/")) {
      return {
        isValid: false,
        hint: "Repository must be in owner/repo format (e.g., airweave-ai/airweave)",
        severity: "warning",
      };
    }

    const parts = trimmed.split("/");
    if (parts.length !== 2) {
      return {
        isValid: false,
        hint: "Repository must be in owner/repo format (e.g., airweave-ai/airweave)",
        severity: "warning",
      };
    }

    const [owner, repo] = parts;
    if (!owner || !repo) {
      return {
        isValid: false,
        hint: "Both owner and repository name must be non-empty",
        severity: "warning",
      };
    }

    // Check for valid characters
    const validPattern = /^[a-zA-Z0-9_-]+\/[a-zA-Z0-9_.-]+$/;
    if (!validPattern.test(trimmed)) {
      return {
        isValid: false,
        hint: "Use only letters, numbers, hyphens, underscores, and dots",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Workspace validation (for Bitbucket, etc.)
 */
export const workspaceValidation: FieldValidation<string> = {
  field: "workspace",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check for valid characters
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: "Workspace can only contain letters, numbers, hyphens, and underscores",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Repository slug validation (for Bitbucket repo_slug)
 */
export const repoSlugValidation: FieldValidation<string> = {
  field: "repo_slug",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check for valid characters (includes dots for repo slugs)
    if (!/^[a-zA-Z0-9_.-]+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: "Repository slug can only contain letters, numbers, hyphens, underscores, and dots",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Database host validation (no protocol required)
 */
export const databaseHostValidation: FieldValidation<string> = {
  field: "host",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Host should NOT include protocol
    if (
      trimmed.startsWith("http://") ||
      trimmed.startsWith("https://") ||
      trimmed.includes("://")
    ) {
      return {
        isValid: false,
        hint: 'Host should not include protocol (e.g., use "localhost" not "postgresql://localhost")',
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Database port validation
 */
export const databasePortValidation: FieldValidation<string> = {
  field: "port",
  debounceMs: 300,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check if the entire string is numeric (reject "123abc")
    if (!/^\d+$/.test(trimmed)) {
      return {
        isValid: false,
        hint: "Port must be a number",
        severity: "warning",
      };
    }

    const port = parseInt(trimmed, 10);
    if (port < 1 || port > 65535) {
      return {
        isValid: false,
        hint: "Port must be between 1 and 65535",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Database tables validation
 */
export const databaseTablesValidation: FieldValidation<string> = {
  field: "tables",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return {
        isValid: false,
        hint: 'Tables field is required (use "*" for all tables)',
        severity: "info",
      };
    }

    // Allow * for all tables
    if (trimmed === "*") {
      return { isValid: true, severity: "info" };
    }

    // Split by comma and validate each table name
    const tables = trimmed.split(",").map((t) => t.trim());
    for (const table of tables) {
      if (!table) {
        return {
          isValid: false,
          hint: "Empty table name in list",
          severity: "warning",
        };
      }
      // Check for valid characters (alphanumeric, underscore, dot)
      if (!/^[a-zA-Z0-9_.]+$/.test(table)) {
        return {
          isValid: false,
          hint: "Table names can only contain letters, numbers, underscores, and dots",
          severity: "warning",
        };
      }
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * GitHub Personal Access Token validation
 */
export const githubTokenValidation: FieldValidation<string> = {
  field: "personal_access_token",
  debounceMs: 0,
  showOn: "blur",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    // Check for valid GitHub token formats
    const isClassicToken = trimmed.startsWith("ghp_");
    const isFineGrainedToken = trimmed.startsWith("github_pat_");
    const isLegacyToken =
      trimmed.length === 40 && /^[0-9a-fA-F]+$/.test(trimmed);

    if (!isClassicToken && !isFineGrainedToken && !isLegacyToken) {
      return {
        isValid: false,
        hint: 'GitHub token should start with "ghp_" (classic) or "github_pat_" (fine-grained)',
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Stripe API key validation
 */
export const stripeApiKeyValidation: FieldValidation<string> = {
  field: "api_key",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    if (!trimmed.startsWith("sk_test_") && !trimmed.startsWith("sk_live_")) {
      return {
        isValid: false,
        hint: 'Stripe API key must start with "sk_test_" or "sk_live_"',
        severity: "warning",
      };
    }

    if (trimmed.length < 20) {
      return {
        isValid: false,
        hint: "Stripe API key appears too short",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Get validation for a specific auth field type
 * @param fieldType - The name of the field to validate
 * @param sourceShortName - Optional source short name for source-specific validations
 */
export function getAuthFieldValidation(
  fieldType: string,
  sourceShortName?: string
): FieldValidation<string> | null {
  // Source-specific validations for common field names
  if (fieldType === "api_key" && sourceShortName === "stripe") {
    return stripeApiKeyValidation;
  }

  switch (fieldType) {
    // API keys and tokens
    case "api_key":
      return apiKeyValidation;
    case "token":
    case "access_token":
      return apiKeyValidation;
    case "personal_access_token":
      return githubTokenValidation;

    // URLs
    case "url":
    case "endpoint":
    case "base_url":
    case "cluster_url":
    case "uri":
      return urlValidation;

    // Database fields
    case "host":
      return databaseHostValidation;
    case "port":
      return databasePortValidation;
    case "tables":
      return databaseTablesValidation;

    // User credentials
    case "email":
    case "username":
      return emailValidation;
    case "client_id":
      return clientIdValidation;
    case "client_secret":
      return clientSecretValidation;

    // Source-specific fields
    case "repo_name":
      return repoNameValidation;
    case "workspace":
      return workspaceValidation;
    case "repo_slug":
      return repoSlugValidation;

    // Auth provider fields
    case "auth_config_id":
      return authConfigIdValidation;
    case "account_id":
      return accountIdValidation;
    case "workflow_id":
      return workflowIdValidation;
    case "project_id":
      return projectIdValidation;
    case "environment":
      return environmentValidation;
    case "external_user_id":
      return externalUserIdValidation;

    default:
      return null;
  }
}

/**
 * Organization name validation
 * Requirements: 2-100 characters
 */
export const organizationNameValidation: FieldValidation<string> = {
  field: "organizationName",
  debounceMs: 500,
  showOn: "change",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: "info" };
    }

    if (trimmed.length < 2) {
      return {
        isValid: false,
        hint: `${2 - trimmed.length} more character${2 - trimmed.length > 1 ? "s" : ""} needed`,
        severity: "info",
      };
    }

    if (trimmed.length > 100) {
      return {
        isValid: false,
        hint: "Maximum 100 characters",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};

/**
 * Required field validation (generic)
 * For fields that just need to be non-empty
 */
export const requiredValidation: FieldValidation<string> = {
  field: "required",
  showOn: "blur",
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return {
        isValid: false,
        hint: "This field is required",
        severity: "warning",
      };
    }

    return { isValid: true, severity: "info" };
  },
};
