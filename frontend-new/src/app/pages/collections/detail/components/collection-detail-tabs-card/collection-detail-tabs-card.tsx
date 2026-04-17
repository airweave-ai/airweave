import * as React from 'react';
import { Link } from '@tanstack/react-router';
import { IconPlus } from '@tabler/icons-react';
import { ConnectionsTabContent } from './connections-tab-content';
import type { SourceConnectionListItem } from '@/shared/api';
import { formatCount } from '@/shared/format/format-count';
import { pluralize } from '@/shared/format/pluralize';
import { Button } from '@/shared/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';
import { Tabs, TabsList, TabsTrigger } from '@/shared/ui/tabs';

type CollectionDetailTabsCardProps = {
  collectionId: string;
  sourceConnections: Array<SourceConnectionListItem>;
};

type CollectionDetailTab = 'connections' | 'events' | 'queries';

export function CollectionDetailTabsCard({
  collectionId,
  sourceConnections,
}: CollectionDetailTabsCardProps) {
  const sourceCount = sourceConnections.length;
  const entityCount = sourceConnections.reduce(
    (total, sourceConnection) => total + (sourceConnection.entity_count ?? 0),
    0,
  );
  const [selectedTab, setSelectedTab] =
    React.useState<CollectionDetailTab>('connections');

  return (
    <Card className="rounded-sm bg-foreground/5 ring-0">
      <CardHeader>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-0.5">
            <CardTitle>Collection Details</CardTitle>
            <CardDescription className="flex items-center gap-1.5 font-mono">
              <span>
                {formatCount(sourceCount)} {pluralize(sourceCount, 'Source')}
              </span>
              <span className="size-[3px] rounded-full bg-current" />
              <span>
                {formatCount(entityCount)}{' '}
                {pluralize(entityCount, 'Entity', 'Entities')}
              </span>
            </CardDescription>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Tabs
              className="w-full sm:w-auto"
              value={selectedTab}
              onValueChange={(value) =>
                setSelectedTab(value as CollectionDetailTab)
              }
            >
              <TabsList className="w-full sm:w-80">
                <TabsTrigger value="connections">Connections</TabsTrigger>
                <TabsTrigger value="events">Events</TabsTrigger>
                <TabsTrigger value="queries">Queries</TabsTrigger>
              </TabsList>
            </Tabs>

            <Button asChild variant="secondary">
              <Link
                params={{ collectionId }}
                to="/collections/$collectionId/connect-source"
              >
                <IconPlus className="size-4" />
                Add Source
              </Link>
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {selectedTab === 'connections' && (
          <ConnectionsTabContent
            collectionId={collectionId}
            sourceConnections={sourceConnections}
          />
        )}
      </CardContent>
    </Card>
  );
}
