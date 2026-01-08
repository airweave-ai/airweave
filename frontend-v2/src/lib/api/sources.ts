/**
 * Source operations
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

/**
 * Auth field definition for a source
 */
export interface AuthField {
  name: string;
  display_name: string;
  field_type: string;
  required: boolean;
  description?: string;
}

/**
 * Config field definition for a source
 */
export interface ConfigField {
  name: string;
  display_name: string;
  field_type: string;
  required: boolean;
  description?: string;
  default?: string | number | boolean;
}

/**
 * Source type matching the backend schema
 */
export interface Source {
  id: string;
  name: string;
  short_name: string;
  description?: string | null;
  auth_type?: string;
  auth_methods?: string[];
  labels?: string[];
  auth_fields?: { fields: AuthField[] };
  config_fields?: { fields: ConfigField[] };
  supported_auth_providers?: string[];
  requires_byoc?: boolean;
}

/**
 * Fetch all available sources
 */
export async function fetchSources(
  token: string,
  orgId: string
): Promise<Source[]> {
  const response = await fetch(`${API_BASE_URL}/sources/`, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch sources"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Fetch a single source by short name
 */
export async function fetchSource(
  token: string,
  orgId: string,
  shortName: string
): Promise<Source> {
  const response = await fetch(`${API_BASE_URL}/sources/${shortName}`, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch source"
    );
    throw new Error(message);
  }

  return response.json();
}


