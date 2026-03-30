import { Spinner } from '@/shared/ui/spinner';

type AuthStatusScreenProps = {
  description: string;
  title: string;
};

export function AuthStatusScreen({
  description,
  title,
}: AuthStatusScreenProps) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-muted/20 p-6 text-center">
      <Spinner className="size-8 text-muted-foreground" />
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </main>
  );
}
