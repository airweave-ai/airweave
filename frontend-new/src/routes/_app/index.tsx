import { Button } from '@/components/ui/button';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_app/')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-950 px-6 py-16 text-white">
      <Button className="w-full">Button</Button>
    </main>
  );
}
