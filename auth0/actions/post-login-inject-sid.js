// Auth0 Action: Post Login
// Injects the Auth0 session ID into the access token as a
// namespaced custom claim, enabling per-session tracking.
//
// NOTE: `event.session` requires an Auth0 Enterprise plan with
// "Sessions with Actions" enabled. On lower-tier plans the
// property is undefined and the claim will not be set.
//
// Deploy: Auth0 Dashboard -> Actions -> Triggers -> Login /
//         Post Login -> Add this Action

/**
 * @param {Event} event - Details about the user and the context in which they are logging in.
 * @param {PostLoginAPI} api - Interface whose methods can be used to change the behavior of the login.
 */
exports.onExecutePostLogin = async (event, api) => {
  if (event.session) {
    api.accessToken.setCustomClaim(
      "https://airweave.ai/sid",
      event.session.id
    );
  } else {
    console.log(
      "event.session is undefined — Sessions with Actions requires an Enterprise plan"
    );
  }
};
