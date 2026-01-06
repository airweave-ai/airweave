import { af as API_BASE_URL, ag as getAuthHeaders } from "./router-BGxBdlkD.mjs";
async function fetchApiKeys(token, orgId, skip = 0, limit = 20) {
  const response = await fetch(
    `${API_BASE_URL}/api-keys?skip=${skip}&limit=${limit}`,
    {
      headers: getAuthHeaders(token, orgId)
    }
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch API keys: ${response.status}`);
  }
  return response.json();
}
async function deleteApiKey(token, orgId, keyId) {
  const response = await fetch(`${API_BASE_URL}/api-keys?id=${keyId}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    throw new Error(`Failed to delete API key: ${response.status}`);
  }
}
async function createApiKey(token, orgId, expirationDays) {
  const response = await fetch(`${API_BASE_URL}/api-keys`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(
      expirationDays ? { expiration_days: expirationDays } : {}
    )
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    if (errorBody?.errors && Array.isArray(errorBody.errors)) {
      const messages = errorBody.errors.map((err) => Object.values(err).join(", ")).join("; ");
      throw new Error(messages);
    }
    throw new Error(`Failed to create API key: ${response.status}`);
  }
  return response.json();
}
export {
  createApiKey as c,
  deleteApiKey as d,
  fetchApiKeys as f
};
