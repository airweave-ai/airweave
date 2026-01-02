/**
 * Safe logging utilities for authentication flows.
 *
 * These utilities ensure that sensitive credential data (passwords, tokens, API keys, etc.)
 * is never exposed in browser console logs, while still providing useful debugging information
 * through metadata logging (field counts, field names, data types).
 *
 * This is part of CASA-48 compliance: "Verify the application does not log credentials or payment details."
 */

/**
 * Regex pattern to detect sensitive field names.
 * Matches: token, key, secret, password, credential, client_id, client_secret, api_key, etc.
 */
const SENSITIVE_FIELD_PATTERN = /(?:token|key|secret|password|credential|client_id|client_secret|api_key|auth|access|refresh|bearer|private)/i;

/**
 * Check if a field name indicates sensitive data.
 */
function isSensitiveField(fieldName: string): boolean {
    return SENSITIVE_FIELD_PATTERN.test(fieldName);
}

/**
 * Safely log authentication values without exposing sensitive data.
 * Logs only metadata: total count, sensitive/non-sensitive field counts, and field names.
 *
 * @param authValues - Dictionary of authentication values
 * @param prefix - Optional prefix for the log message (e.g., '🔐 [Component]')
 *
 * @example
 * safeLogAuthValues(authValues, '🔐 [SemanticMcp]');
 * // Output: 🔐 [SemanticMcp] Auth values - Total: 3, Sensitive: 2, Non-sensitive: 1
 */
export function safeLogAuthValues(
    authValues: Record<string, any> | null | undefined,
    prefix: string = '🔐'
): void {
    if (!authValues || Object.keys(authValues).length === 0) {
        console.log(`${prefix} Auth values - Empty`);
        return;
    }

    const allKeys = Object.keys(authValues);
    const sensitiveFields = allKeys.filter(key => isSensitiveField(key));
    const nonSensitiveFields = allKeys.filter(key => !isSensitiveField(key));

    console.log(
        `${prefix} Auth values - Total: ${allKeys.length}, Sensitive: ${sensitiveFields.length}, Non-sensitive: ${nonSensitiveFields.length}`
    );
}

/**
 * Safely log a dialog state object by logging safe metadata for authValues
 * and other non-sensitive properties.
 *
 * @param dialogState - Dialog state object that may contain authValues and other properties
 * @param prefix - Optional prefix for the log message
 *
 * @example
 * safeLogDialogState(dialogState, '📊 [Component]');
 */
export function safeLogDialogState(
    dialogState: Record<string, any> | null | undefined,
    prefix: string = '📊'
): void {
    if (!dialogState) {
        console.log(`${prefix} Dialog state - Empty`);
        return;
    }

    // Extract authValues if present
    const { authValues, configValues, ...safeState } = dialogState;

    // Log safe properties (everything except authValues)
    const safeKeys = Object.keys(safeState);
    console.log(`${prefix} Dialog state - Safe properties: ${safeKeys.length} keys`);

    // Separately log authValues safely
    if (authValues) {
        safeLogAuthValues(authValues, `${prefix} Dialog state authValues:`);
    }

    // Log configValues (usually not sensitive, but log keys only to be safe)
    if (configValues) {
        const configKeys = Object.keys(configValues);
        console.log(`${prefix} Dialog state configValues - Keys: ${configKeys.length}`);
    }
}

/**
 * Safely log credential data being sent to the API.
 * Logs structure without exposing auth_fields values.
 *
 * @param credentialData - Credential data object containing auth_fields
 * @param prefix - Optional prefix for the log message
 *
 * @example
 * safeLogCredentialData(credentialData, '📤 [Component]');
 */
export function safeLogCredentialData(
    credentialData: Record<string, any> | null | undefined,
    prefix: string = '📤'
): void {
    if (!credentialData) {
        console.log(`${prefix} Credential data - Empty`);
        return;
    }

    const { auth_fields, ...safeData } = credentialData;

    // Log safe properties
    console.log(`${prefix} Credential data - Structure:`, {
        ...safeData,
        auth_fields: auth_fields ? `<${Object.keys(auth_fields).length} fields>` : undefined
    });

    // Separately log auth_fields safely
    if (auth_fields) {
        safeLogAuthValues(auth_fields, `${prefix} Credential auth_fields:`);
    }
}

/**
 * Safely log a single sensitive value (like client_id) by showing only metadata.
 *
 * @param value - The sensitive value
 * @param fieldName - Name of the field being logged
 * @param prefix - Optional prefix for the log message
 *
 * @example
 * safeLogSensitiveValue(authValues.client_id, 'client_id', '🔑');
 * // Output: 🔑 client_id: <string, 24 chars>
 */
export function safeLogSensitiveValue(
    value: any,
    fieldName: string,
    prefix: string = '🔑'
): void {
    if (value === null || value === undefined) {
        console.log(`${prefix} ${fieldName}: <null>`);
        return;
    }

    const valueType = typeof value;
    let metadata = `<${valueType}>`;

    if (typeof value === 'string') {
        metadata = `<${valueType}, ${value.length} chars>`;
    } else if (typeof value === 'number' || typeof value === 'boolean') {
        metadata = `<${valueType}>`;
    }

    console.log(`${prefix} ${fieldName}: ${metadata}`);
}
