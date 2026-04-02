import { AlertTriangle, RefreshCw } from 'lucide-react';
import { env } from '@/shared/config/env';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';
import { Button } from '@/shared/ui/button';

type AuthErrorPageProps = {
  error: Error;
  onReload: () => void;
};

export function AuthErrorPage({ error, onReload }: AuthErrorPageProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <Card className="w-full max-w-lg rounded-3xl border-border/70 shadow-sm">
        <CardHeader className="space-y-4">
          <div className="flex size-12 items-center justify-center rounded-2xl border bg-destructive/10 text-destructive shadow-sm">
            <AlertTriangle className="size-6" />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl">
              Couldn't complete sign in
            </CardTitle>
            <CardDescription>
              Airweave could not finish authentication. Please try again in a
              moment.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Reload the app to try signing in again.
          </p>
          {env.DEV && error.message ? (
            <div className="rounded-2xl border bg-muted/50 px-4 py-3 font-mono text-xs text-muted-foreground">
              {error.message}
            </div>
          ) : null}
          <Button className="w-full" onClick={onReload} size="lg">
            <RefreshCw />
            Reload app
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
