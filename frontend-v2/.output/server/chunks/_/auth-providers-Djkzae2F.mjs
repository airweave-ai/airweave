import { af as API_BASE_URL, ag as getAuthHeaders, ah as parseErrorResponse } from "./router-BGxBdlkD.mjs";
async function fetchAuthProviders(token, orgId) {
  const response = await fetch(`${API_BASE_URL}/auth-providers/list`, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch auth providers: ${response.status}`);
  }
  return response.json();
}
async function fetchAuthProviderConnections(token, orgId) {
  const response = await fetch(`${API_BASE_URL}/auth-providers/connections/`, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    throw new Error(
      `Failed to fetch auth provider connections: ${response.status}`
    );
  }
  return response.json();
}
async function fetchAuthProviderDetail(token, orgId, shortName) {
  const response = await fetch(
    `${API_BASE_URL}/auth-providers/detail/${shortName}`,
    {
      headers: getAuthHeaders(token, orgId)
    }
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch auth provider details: ${response.status}`
    );
  }
  return response.json();
}
async function fetchAuthProviderConnection(token, orgId, readableId) {
  const response = await fetch(
    `${API_BASE_URL}/auth-providers/connections/${readableId}`,
    {
      headers: getAuthHeaders(token, orgId)
    }
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch auth provider connection: ${response.status}`
    );
  }
  return response.json();
}
async function createAuthProviderConnection(token, orgId, data) {
  const response = await fetch(`${API_BASE_URL}/auth-providers/`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const errorMessage = await parseErrorResponse(
      response,
      `Failed to create auth provider connection: ${response.status}`
    );
    throw new Error(errorMessage);
  }
  return response.json();
}
async function updateAuthProviderConnection(token, orgId, readableId, data) {
  const response = await fetch(`${API_BASE_URL}/auth-providers/${readableId}`, {
    method: "PUT",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const errorMessage = await parseErrorResponse(
      response,
      `Failed to update auth provider connection: ${response.status}`
    );
    throw new Error(errorMessage);
  }
  return response.json();
}
async function deleteAuthProviderConnection(token, orgId, readableId) {
  const response = await fetch(`${API_BASE_URL}/auth-providers/${readableId}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    throw new Error(
      `Failed to delete auth provider connection: ${response.status}`
    );
  }
}
export {
  fetchAuthProviderConnections as a,
  fetchAuthProviderDetail as b,
  createAuthProviderConnection as c,
  fetchAuthProviderConnection as d,
  deleteAuthProviderConnection as e,
  fetchAuthProviders as f,
  updateAuthProviderConnection as u
};
