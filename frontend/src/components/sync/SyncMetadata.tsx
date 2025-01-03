import { Card } from "@/components/ui/card";
import { Calendar, Activity, Clock, User, Building2, Mail } from "lucide-react";
import { format } from "date-fns";

interface SyncMetadataProps {
  sync: any; // Replace with proper type
}

export const SyncMetadata = ({ sync }: SyncMetadataProps) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card className="p-6 space-y-2">
        <div className="flex items-center text-muted-foreground">
          <Calendar className="mr-2 h-4 w-4" />
          Created
        </div>
        <p className="text-2xl font-semibold">
          {format(new Date(sync.createdAt), "MMM d, yyyy")}
        </p>
      </Card>
      <Card className="p-6 space-y-2">
        <div className="flex items-center text-muted-foreground">
          <Activity className="mr-2 h-4 w-4" />
          Total Runs
        </div>
        <p className="text-2xl font-semibold">{sync.totalRuns}</p>
      </Card>
      <Card className="p-6 space-y-2">
        <div className="flex items-center text-muted-foreground">
          <Clock className="mr-2 h-4 w-4" />
          Schedule
        </div>
        <p className="text-2xl font-semibold">{sync.schedule}</p>
      </Card>

      <Card className="p-6 space-y-4 md:col-span-3">
        <h3 className="text-lg font-semibold">White Label Information</h3>
        <div className="grid gap-4">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">User ID:</span>
            <span className="text-muted-foreground">{sync.metadata.userId}</span>
          </div>
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">Organization ID:</span>
            <span className="text-muted-foreground">{sync.metadata.organizationId}</span>
          </div>
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">Email:</span>
            <span className="text-muted-foreground">{sync.metadata.email}</span>
          </div>
        </div>
      </Card>
    </div>
  );
};