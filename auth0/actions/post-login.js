// Auth0 Action: Post Login
// Injects custom claims into the access token for downstream backend
// consumption.  Deploy under Actions -> Triggers -> Login / Post Login.
//
// Claims added:
//   https://airweave.ai/auth_time — epoch seconds of last interactive login
//                                    (CASA-29: re-auth for sensitive ops)
//
// TODO(CASA-29): When PR #1746 merges, combine with the session-id
// injection from post-login-inject-sid.js into this single Action and
// remove the duplicate file.

/**
 * @param {Event} event - Details about the user and the context.
 * @param {PostLoginAPI} api - Methods to manipulate the login flow.
 */
exports.onExecutePostLogin = async (event, api) => {
  // Authentication timestamp (CASA-29)
  if (event.authentication && event.authentication.authTime) {
    api.accessToken.setCustomClaim(
      "https://airweave.ai/auth_time",
      Math.floor(event.authentication.authTime.getTime() / 1000)
    );
  }
};
