import { CheckCircle, Shield, Clock } from 'lucide-react';
import type { ConnectSessionContext } from '../lib/types';

interface SuccessScreenProps {
  session: ConnectSessionContext;
}

export function SuccessScreen({ session }: SuccessScreenProps) {
  const expiresAt = new Date(session.expires_at);
  const formattedExpiry = expiresAt.toLocaleTimeString();

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-slate-800 rounded-xl p-8 border border-slate-700">
        <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-8 h-8 text-green-400" />
        </div>
        <h1 className="text-2xl font-bold text-white text-center mb-2">
          Session Validated
        </h1>
        <p className="text-gray-400 text-center mb-6">
          Your session is active and ready.
        </p>

        <div className="space-y-4">
          <div className="bg-slate-700/50 rounded-lg p-4">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
              <Shield className="w-4 h-4" />
              Mode
            </div>
            <p className="text-white font-medium capitalize">{session.mode}</p>
          </div>

          <div className="bg-slate-700/50 rounded-lg p-4">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
              <Clock className="w-4 h-4" />
              Expires
            </div>
            <p className="text-white font-medium">{formattedExpiry}</p>
          </div>

          {session.allowed_integrations && (
            <div className="bg-slate-700/50 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-2">Allowed Integrations</p>
              <div className="flex flex-wrap gap-2">
                {session.allowed_integrations.map((integration) => (
                  <span
                    key={integration}
                    className="px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded text-sm"
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
