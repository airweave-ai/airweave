import { Loader2 } from 'lucide-react';

interface LoadingScreenProps {
  message?: string;
}

export function LoadingScreen({ message = 'Loading...' }: LoadingScreenProps) {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: 'var(--connect-bg)' }}
    >
      <div className="text-center">
        <Loader2
          className="w-12 h-12 animate-spin mx-auto mb-4"
          style={{ color: 'var(--connect-primary)' }}
        />
        <p className="text-lg" style={{ color: 'var(--connect-text-muted)' }}>
          {message}
        </p>
      </div>
    </div>
  );
}
