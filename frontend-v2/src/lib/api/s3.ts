/**
 * S3 Configuration API client
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

/**
 * S3 configuration request
 */
export interface S3ConfigRequest {
  aws_access_key_id: string;
  aws_secret_access_key: string;
  bucket_name: string;
  bucket_prefix: string;
  aws_region: string;
  endpoint_url: string | null;
  use_ssl: boolean;
}

/**
 * S3 configuration response
 */
export interface S3ConfigResponse {
  connection_id: string;
  status: "created" | "updated";
  message: string;
}

/**
 * S3 status response
 */
export interface S3Status {
  feature_enabled: boolean;
  configured: boolean;
  connection_id?: string;
  bucket_name?: string;
  status?: string;
  created_at?: string;
  message?: string;
}

/**
 * S3 test result response
 */
export interface S3TestResult {
  status: "success";
  message: string;
  bucket_name: string;
  endpoint: string;
}

/**
 * Fetch S3 configuration status
 */
export async function fetchS3Status(
  token: string,
  organizationId: string
): Promise<S3Status> {
  const response = await fetch(`${API_BASE_URL}/s3/s3/status`, {
    method: "GET",
    headers: getAuthHeaders(token, organizationId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch S3 status"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Test S3 connection without saving
 */
export async function testS3Connection(
  token: string,
  organizationId: string,
  config: S3ConfigRequest
): Promise<S3TestResult> {
  const response = await fetch(`${API_BASE_URL}/s3/test`, {
    method: "POST",
    headers: getAuthHeaders(token, organizationId),
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "S3 connection test failed"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Configure S3 destination
 */
export async function configureS3(
  token: string,
  organizationId: string,
  config: S3ConfigRequest
): Promise<S3ConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/s3/configure`, {
    method: "POST",
    headers: getAuthHeaders(token, organizationId),
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to configure S3"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Delete S3 configuration
 */
export async function deleteS3Config(
  token: string,
  organizationId: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/s3/configure`, {
    method: "DELETE",
    headers: getAuthHeaders(token, organizationId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to delete S3 configuration"
    );
    throw new Error(message);
  }
}
