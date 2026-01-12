import { CheckCircle, Shield, Clock } from 'lucide-react';
import type { ConnectSessionContext } from '../lib/types';

interface SuccessScreenProps {
  session: ConnectSessionContext;
}

export function SuccessScreen({ session }: SuccessScreenProps) {
  const expiresAt = new Date(session.expires_at);
  const formattedExpiry = expiresAt.toLocaleTimeString();

  return (
    <div
      className="min-h-screen flex items-center justify-center p-6"
      style={{ backgroundColor: 'var(--connect-bg)' }}
    >
      <div
        className="max-w-md w-full rounded-xl p-8"
        style={{
          backgroundColor: 'var(--connect-surface)',
          border: '1px solid var(--connect-border)',
        }}
      >
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6"
          style={{ backgroundColor: 'color-mix(in srgb, var(--connect-success) 20%, transparent)' }}
        >
          <CheckCircle className="w-8 h-8" style={{ color: 'var(--connect-success)' }} />
        </div>
        <h1
          className="text-2xl font-bold text-center mb-2"
          style={{ color: 'var(--connect-text)' }}
        >
          Session Validated
        </h1>
        <p
          className="text-center mb-6"
          style={{ color: 'var(--connect-text-muted)' }}
        >
          Your session is active and ready.
        </p>

        <div className="space-y-4">
          <div
            className="rounded-lg p-4"
            style={{ backgroundColor: 'color-mix(in srgb, var(--connect-secondary) 50%, transparent)' }}
          >
            <div
              className="flex items-center gap-2 text-sm mb-1"
              style={{ color: 'var(--connect-text-muted)' }}
            >
              <Shield className="w-4 h-4" />
              Mode
            </div>
            <p className="font-medium capitalize" style={{ color: 'var(--connect-text)' }}>
              {session.mode}
            </p>
          </div>

          <div
            className="rounded-lg p-4"
            style={{ backgroundColor: 'color-mix(in srgb, var(--connect-secondary) 50%, transparent)' }}
          >
            <div
              className="flex items-center gap-2 text-sm mb-1"
              style={{ color: 'var(--connect-text-muted)' }}
            >
              <Clock className="w-4 h-4" />
              Expires
            </div>
            <p className="font-medium" style={{ color: 'var(--connect-text)' }}>
              {formattedExpiry}
            </p>
          </div>

          {session.allowed_integrations && (
            <div
              className="rounded-lg p-4"
              style={{ backgroundColor: 'color-mix(in srgb, var(--connect-secondary) 50%, transparent)' }}
            >
              <p
                className="text-sm mb-2"
                style={{ color: 'var(--connect-text-muted)' }}
              >
                Allowed Integrations
              </p>
              <div className="flex flex-wrap gap-2">
                {session.allowed_integrations.map((integration) => (
                  <span
                    key={integration}
                    className="px-2 py-1 rounded text-sm"
                    style={{
                      backgroundColor: 'color-mix(in srgb, var(--connect-primary) 20%, transparent)',
                      color: 'var(--connect-primary)',
                    }}
                  >
                    {integration}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
