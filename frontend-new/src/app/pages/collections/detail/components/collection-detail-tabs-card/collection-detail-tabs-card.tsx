import * as React from 'react';
import { Link } from '@tanstack/react-router';
import { IconPlus } from '@tabler/icons-react';
import { ConnectionsTabContent } from './connections-tab-content';
import type { SourceConnectionListItem } from '@/shared/api';
import { formatNumber } from '@/shared/format/format-number';
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
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1 basis-56 space-y-0.5">
            <CardTitle>Collection Details</CardTitle>
            <CardDescription className="flex items-center gap-1.5 font-mono">
              <span>
                {formatNumber(sourceCount)} {pluralize(sourceCount, 'Source')}
              </span>
              <span className="size-[3px] rounded-full bg-current" />
              <span>
                {formatNumber(entityCount)}{' '}
                {pluralize(entityCount, 'Entity', 'Entities')}
              </span>
            </CardDescription>
          </div>

          <div className="flex min-w-0 flex-1 basis-72 flex-wrap items-center justify-start gap-2 sm:justify-end">
            <Tabs
              className="min-w-0 flex-1 basis-64 lg:max-w-80"
              value={selectedTab}
              onValueChange={(value) =>
                setSelectedTab(value as CollectionDetailTab)
              }
            >
              <TabsList className="w-full">
                <TabsTrigger value="connections">Connections</TabsTrigger>
                <TabsTrigger value="events">Events</TabsTrigger>
                <TabsTrigger value="queries">Queries</TabsTrigger>
              </TabsList>
            </Tabs>

            <Button asChild variant="secondary" className="shrink-0">
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
