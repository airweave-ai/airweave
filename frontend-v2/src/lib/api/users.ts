/**
 * Users API client
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export interface User {
  id: string;
  email: string;
  name?: string;
  is_admin: boolean;
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
