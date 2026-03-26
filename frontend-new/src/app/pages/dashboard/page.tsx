import { Plus, Search } from 'lucide-react';
import { Button } from '@/shared/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { PageShell } from '@/shared/ui/page-shell';

export function DashboardPage() {
  return (
    <PageShell
      description="Start with a minimal dashboard surface and grow feature slices only when the UI becomes reusable."
      title="Dashboard"
    >
      <Card>
        <CardHeader>
          <CardTitle>Collections</CardTitle>
          <CardDescription>
            Search your synced knowledge and create a new collection.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 md:flex-row md:items-center">
          <InputGroup className="md:max-w-md">
            <InputGroupInput placeholder="Search collections..." />
            <InputGroupAddon align="inline-end">
              <Search className="size-4 text-accent-foreground" />
            </InputGroupAddon>
          </InputGroup>

          <Button className="md:ml-auto" size="lg">
            <Plus />
            Create Collection
          </Button>
        </CardContent>
      </Card>
    </PageShell>
  );
}
