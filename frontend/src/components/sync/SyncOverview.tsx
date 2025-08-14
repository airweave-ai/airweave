import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SyncUIMetadata } from "./types";
import { InfoIcon } from "lucide-react";

interface SyncOverviewProps {
  syncMetadata: SyncUIMetadata | null;
}

export function SyncOverview({ syncMetadata }: SyncOverviewProps) {
  if (!syncMetadata) return null;

  const { source, destination } = syncMetadata;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <InfoIcon className="h-5 w-5 text-primary" />
          Sync Overview
        </CardTitle>
        <CardDescription>
          Here's what will happen when you start this sync
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="rounded-md bg-muted p-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Data will be synchronized from{" "}
              <span className="font-medium text-foreground">{source.name}</span>{" "}
              to{" "}
              <span className="font-medium text-foreground">
                {destination.name}
              </span>
              . The system will extract content, process it through the pipeline
              configured below, and make it available for search and retrieval
              in your vector database.
            </p>
            <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
              You can modify the pipeline stages to customize how your data is
              processed before being stored.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
