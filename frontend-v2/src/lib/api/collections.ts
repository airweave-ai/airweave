/**
 * Collection operations
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

/**
 * Collection type matching the backend schema
 */
export interface Collection {
  id: string;
  name: string;
  readable_id: string;
  vector_size: number;
  embedding_model_name: string;
  created_at: string;
  modified_at: string;
  organization_id: string;
  created_by_email: string | null;
  modified_by_email: string | null;
  status: "NEEDS_SOURCE" | "ACTIVE" | "ERROR";
}

/**
 * Request type for creating a collection
 */
export interface CreateCollectionRequest {
  name: string;
  readable_id?: string;
}

/**
 * Fetch collections for the current organization with pagination
 */
export async function fetchCollections(
  token: string,
  orgId: string,
  skip = 0,
  limit = 100,
  search?: string
): Promise<Collection[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  if (search) {
    params.append("search", search);
  }

  const response = await fetch(`${API_BASE_URL}/collections?${params}`, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch collections"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Get a single collection by readable ID
 */
export async function fetchCollection(
  token: string,
  orgId: string,
  readableId: string
): Promise<Collection> {
  const response = await fetch(`${API_BASE_URL}/collections/${readableId}`, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch collection"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Create a new collection
 */
export async function createCollection(
  token: string,
  orgId: string,
  data: CreateCollectionRequest
): Promise<Collection> {
  const response = await fetch(`${API_BASE_URL}/collections`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create collection"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Delete a collection by readable ID
 */
export async function deleteCollection(
  token: string,
  orgId: string,
  readableId: string
): Promise<Collection> {
  const response = await fetch(`${API_BASE_URL}/collections/${readableId}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to delete collection"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Get collection count
 */
export async function fetchCollectionCount(
  token: string,
  orgId: string,
  search?: string
): Promise<number> {
  const params = new URLSearchParams();
  if (search) {
    params.append("search", search);
  }

  const response = await fetch(`${API_BASE_URL}/collections/count?${params}`, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch collection count"
    );
    throw new Error(message);
  }

  return response.json();
}
