import { OAuthRegisteredClientsStore } from '@modelcontextprotocol/sdk/server/auth/clients.js';
import { OAuthClientInformationFull } from '@modelcontextprotocol/sdk/shared/auth.js';

export class InMemoryClientsStore implements OAuthRegisteredClientsStore {
    private readonly clients = new Map<string, OAuthClientInformationFull>();

    getClient(clientId: string): OAuthClientInformationFull | undefined {
        return this.clients.get(clientId);
    }

    registerClient(client: OAuthClientInformationFull): OAuthClientInformationFull {
        this.clients.set(client.client_id, client);
        return client;
    }
}
