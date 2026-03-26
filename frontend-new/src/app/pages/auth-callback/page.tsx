import { LoaderCircle } from 'lucide-react';

export function AuthCallbackPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-muted/20 p-6 text-center">
      <LoaderCircle className="size-8 animate-spin text-muted-foreground" />
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">Finishing sign-in</h1>
        <p className="text-sm text-muted-foreground">
          You will be redirected back to the app in a moment.
        </p>
      </div>
    </main>
  );
}
