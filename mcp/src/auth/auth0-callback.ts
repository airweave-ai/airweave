import type { Request, Response } from 'express';
import { Auth0OAuthProvider } from './auth0-provider.js';
import { safeLogObject } from './security.js';

export function createAuth0CallbackHandler(provider: Auth0OAuthProvider) {
    return async (req: Request, res: Response): Promise<void> => {
        const state = typeof req.query.state === 'string' ? req.query.state : undefined;
        const code = typeof req.query.code === 'string' ? req.query.code : undefined;

        if (!state || !code) {
            res.status(400).json({ error: 'missing state or code' });
            return;
        }

        try {
            const result = await provider.exchangeAuth0CodeForLocalCode(state, code);
            const redirect = new URL(result.redirectUri);
            redirect.searchParams.set('code', result.code);
            if (result.state) {
                redirect.searchParams.set('state', result.state);
            }
            res.redirect(302, redirect.toString());
        } catch (error) {
            console.error(
                `[${new Date().toISOString()}] OAuth callback failed:`,
                safeLogObject({
                    state,
                    error: error instanceof Error ? error.message : 'unknown',
                })
            );
            res.status(400).json({ error: 'oauth_callback_failed' });
        }
    };
}
