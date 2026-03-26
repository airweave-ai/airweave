import { Building2, LogOut } from 'lucide-react';
import { useAuth } from '@/shared/auth';
import { Button } from '@/shared/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';

export function OnboardingPage() {
  const auth = useAuth();

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <Card className="w-full max-w-lg rounded-3xl border-border/70 shadow-sm">
        <CardHeader className="space-y-4">
          <div className="flex size-12 items-center justify-center rounded-2xl border bg-background shadow-sm">
            <Building2 className="size-6" />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl">
              Finish organization setup
            </CardTitle>
            <CardDescription>
              You are signed in, but your account does not belong to an
              organization yet. This onboarding flow is still a placeholder in
              `frontend-new`.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            For now, create an organization in the existing frontend or sign out
            and switch to an account that already has one.
          </p>
          <Button
            className="w-full"
            onClick={auth.logout}
            size="lg"
            variant="outline"
          >
            <LogOut />
            Sign out
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
