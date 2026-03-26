import { LogIn, ShieldCheck } from 'lucide-react';
import { useAuth } from '@/shared/auth';
import { Button } from '@/shared/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';

type LoginPageProps = {
  redirect?: string;
};

export function LoginPage({ redirect }: LoginPageProps) {
  const auth = useAuth();

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <Card className="w-full max-w-md rounded-3xl border-border/70 shadow-sm">
        <CardHeader className="space-y-4">
          <div className="flex size-12 items-center justify-center rounded-2xl border bg-background shadow-sm">
            <ShieldCheck className="size-6" />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl">Sign in to Airweave</CardTitle>
            <CardDescription>
              Keep TanStack file routes declarative and page UI inside
              `src/app/pages/login`.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <Button
            className="w-full"
            onClick={() => auth.login(getLoginRedirectTarget(redirect))}
            size="lg"
          >
            <LogIn />
            Continue with Auth0
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}

function getLoginRedirectTarget(redirect?: string) {
  if (!redirect) {
    return undefined;
  }

  if (redirect.startsWith('http://') || redirect.startsWith('https://')) {
    return redirect;
  }

  return `${window.location.origin}${redirect.startsWith('/') ? redirect : `/${redirect}`}`;
}
