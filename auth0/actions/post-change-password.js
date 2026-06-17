// Auth0 Action: Post Change Password
// Calls the Airweave backend webhook to revoke all sessions and
// refresh tokens when a user changes their password.
//
// Secrets required:
//   AIRWEAVE_API_URL       - e.g. https://app.airweave.ai
//   AIRWEAVE_WEBHOOK_SECRET - shared secret matching backend config
//
// Deploy: Auth0 Dashboard -> Actions -> Triggers -> Password /
//         Post Change Password -> Add this Action

/**
 * @param {Event} event - Details about the user whose password was changed.
 * @param {PostChangePasswordAPI} api - Methods to affect the post-change-password flow.
 */
exports.onExecutePostChangePassword = async (event, api) => {
  const url = event.secrets.AIRWEAVE_API_URL;

  if (!url) {
    console.log("AIRWEAVE_API_URL secret is not configured");
    return;
  }

  if (url.startsWith("http://")) {
    console.log("Refusing to send webhook secret over plaintext HTTP");
    return;
  }

  const maxAttempts = 3;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const response = await fetch(
        `${url}/webhooks/auth0/password-changed`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Auth0-Webhook-Secret": event.secrets.AIRWEAVE_WEBHOOK_SECRET,
          },
          body: JSON.stringify({ auth0_id: event.user.user_id }),
          signal: AbortSignal.timeout(5000),
        }
      );

      if (response.ok) return;
      console.log(`webhook attempt ${attempt}/${maxAttempts} failed: ${response.status}`);
    } catch (err) {
      console.log(
        `webhook attempt ${attempt}/${maxAttempts} failed: ${err.cause?.code ?? "no response"}`
      );
    }
    if (attempt < maxAttempts) {
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt - 1)));
    }
  }
};
