import express from 'express';
import { OAuthTokens } from '@modelcontextprotocol/sdk/shared/auth.js';
import { Auth0OAuthServerProvider } from './auth0-provider.js';

type CallbackResult = {
    authorizationCode: string;
    redirectUri: string;
    originalState?: string;
};

export interface Auth0CallbackProvider {
    getPendingAuthorization(pendingId: string): { redirectUri: string; state?: string } | undefined;
    exchangeAuth0AuthorizationCode(code: string): Promise<OAuthTokens>;
    completeAuthorizationFromPending(pendingId: string, auth0Tokens: OAuthTokens): CallbackResult;
}

function redirectWithError(redirectUri: string, error: string, errorDescription: string, state?: string): string {
    const redirect = new URL(redirectUri);
    redirect.searchParams.set('error', error);
    redirect.searchParams.set('error_description', errorDescription);
    if (state) {
        redirect.searchParams.set('state', state);
    }
    return redirect.toString();
}

export function createAuth0CallbackRouter(provider: Auth0CallbackProvider | Auth0OAuthServerProvider): express.Router {
    const router = express.Router();
    router.get('/auth0/callback', createAuth0CallbackHandler(provider));
    return router;
}

export function createAuth0CallbackHandler(provider: Auth0CallbackProvider | Auth0OAuthServerProvider) {
    return async (req: express.Request, res: express.Response) => {
        const code = typeof req.query.code === 'string' ? req.query.code : undefined;
        const pendingId = typeof req.query.state === 'string' ? req.query.state : undefined;

        if (!code || !pendingId) {
            res.status(400).json({ error: 'missing_required_query_params', details: 'Both code and state are required' });
            return;
        }

        const pending = provider.getPendingAuthorization(pendingId);
        if (!pending) {
            res.status(400).json({ error: 'invalid_state', details: 'Unknown or expired authorization state' });
            return;
        }

        try {
            const auth0Tokens = await provider.exchangeAuth0AuthorizationCode(code);
            const result = provider.completeAuthorizationFromPending(pendingId, auth0Tokens);

            const redirect = new URL(result.redirectUri);
            redirect.searchParams.set('code', result.authorizationCode);
            if (result.originalState) {
                redirect.searchParams.set('state', result.originalState);
            }

            res.redirect(redirect.toString());
        } catch (error) {
            res.redirect(
                redirectWithError(
                    pending.redirectUri,
                    'access_denied',
                    error instanceof Error ? error.message : 'Auth0 code exchange failed',
                    pending.state
                )
            );
        }
    };
}
