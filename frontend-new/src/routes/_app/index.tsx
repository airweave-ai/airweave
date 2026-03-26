import { createFileRoute } from '@tanstack/react-router';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/components/ui/input-group';

export const Route = createFileRoute('/_app/')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <div className="flex gap-1">
      <Card className="flex-2 border-none">
        <CardHeader className="flex items-center gap-3">
          <CardTitle>Collections</CardTitle>
          <InputGroup>
            <InputGroupInput placeholder="Search..." />
            <InputGroupAddon>
              <Search className="text-accent-foreground" />
            </InputGroupAddon>
          </InputGroup>
          <Button size="lg">Create Collection</Button>
        </CardHeader>
      </Card>
    </div>
  );
}
