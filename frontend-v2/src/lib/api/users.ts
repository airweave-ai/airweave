import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export interface User {
  id: string;
  email: string;
  name?: string;
  is_admin: boolean;
}

export interface UserCreate {
  email: string;
  full_name?: string;
  picture?: string;
  auth0_id?: string;
  email_verified?: boolean;
}

export interface Auth0ConflictError {
  error: "auth0_id_conflict";
  message: string;
  existing_auth0_id?: string;
  incoming_auth0_id?: string;
}

export interface CreateOrUpdateUserResult {
  success: boolean;
  user?: User;
  conflictError?: Auth0ConflictError;
  error?: string;
}

/**
 * Fetch the current user's profile
 */
export async function fetchCurrentUser(token: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/users/`, {
    method: "GET",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch user profile"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Create or update user in backend after Auth0 authentication.
 * Returns a result object to handle auth0_id_conflict errors gracefully.
 */
export async function createOrUpdateUser(
  token: string,
  userData: UserCreate
): Promise<CreateOrUpdateUserResult> {
  try {
    const response = await fetch(`${API_BASE_URL}/users/create_or_update`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify(userData),
    });

    if (response.ok) {
      const user = await response.json();
      return { success: true, user };
    }

    // Check for Auth0 ID conflict (409)
    if (response.status === 409) {
      const errorData = await response.json();
      if (errorData.detail?.error === "auth0_id_conflict") {
        return {
          success: false,
          conflictError: {
            error: "auth0_id_conflict",
            message: errorData.detail.message,
            existing_auth0_id: errorData.detail.existing_auth0_id,
            incoming_auth0_id: errorData.detail.incoming_auth0_id,
          },
        };
      }
    }

    // Other errors
    const message = await parseErrorResponse(
      response,
      "Failed to create or update user"
    );
    return { success: false, error: message };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Unknown error occurred",
    };
  }
}
