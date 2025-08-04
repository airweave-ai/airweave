import React, { useState } from "react";
import { SyncScheduleManager } from "@/components/sync/SyncScheduleManager";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

export default function SyncScheduleTest() {
  const [syncId, setSyncId] = useState("");

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold">Sync Schedule Test</h1>
        <p className="text-muted-foreground">
          Test the new incremental sync scheduling functionality
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="syncId">Sync ID</Label>
            <Input
              id="syncId"
              value={syncId}
              onChange={(e) => setSyncId(e.target.value)}
              placeholder="Enter a sync ID to test with"
            />
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">Example:</Badge>
            <code className="text-sm bg-muted px-2 py-1 rounded">
              123e4567-e89b-12d3-a456-426614174000
            </code>
          </div>
        </CardContent>
      </Card>

      {syncId && (
        <SyncScheduleManager
          syncId={syncId}
          initialConfig={{ type: "one-time" }}
          onConfigChange={(config) => {
            console.log("Schedule config changed:", config);
          }}
        />
      )}

      {!syncId && (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">
              Enter a sync ID above to test the schedule management
              functionality
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>API Endpoints</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="text-sm">
            <strong>Create Schedule:</strong> POST /sync/{"{syncId}"}
            /minute-level-schedule
          </div>
          <div className="text-sm">
            <strong>Update Schedule:</strong> PUT /sync/{"{syncId}"}
            /minute-level-schedule
          </div>
          <div className="text-sm">
            <strong>Pause Schedule:</strong> POST /sync/{"{syncId}"}
            /minute-level-schedule/pause
          </div>
          <div className="text-sm">
            <strong>Resume Schedule:</strong> POST /sync/{"{syncId}"}
            /minute-level-schedule/resume
          </div>
          <div className="text-sm">
            <strong>Delete Schedule:</strong> DELETE /sync/{"{syncId}"}
            /minute-level-schedule
          </div>
          <div className="text-sm">
            <strong>Get Schedule:</strong> GET /sync/{"{syncId}"}
            /minute-level-schedule
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
