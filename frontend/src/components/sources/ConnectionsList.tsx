import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Connection } from "@/types";
import { Search, Plus, Unplug, Database, CheckCircle2, AlertCircle, Ban } from "lucide-react";
import { Badge } from "../ui/badge";
import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

interface ConnectionsListProps {
  connections: Connection[];
  search: string;
  onSearchChange: (value: string) => void;
  onConnect: () => void;
}

export function ConnectionsList({
  connections,
  search,
  onSearchChange,
  onConnect,
}: ConnectionsListProps) {
  const [connectionToDelete, setConnectionToDelete] = useState<Connection | null>(null);

  const getStatusIcon = (status: Connection['status']) => {
    console.log('Connection status:', status);

    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'ERROR':
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      case 'INACTIVE':
        return <Ban className="h-4 w-4 text-muted-foreground" />;
      default:
        return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const handleDisconnect = async () => {
    if (!connectionToDelete) return;

    try {
      await apiClient.put(`/connections/disconnect/source/${connectionToDelete.id}`);
      toast.success("Connection disconnected successfully");
    } catch (error) {
      toast.error("Failed to disconnect connection");
    } finally {
      setConnectionToDelete(null);
    }
  };

  return (
    <div className="space-y-6 pt-4">
      <div className="flex items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search connections..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <ScrollArea className="h-[400px] pr-4">
        <div className="grid gap-4">
          {connections.map((connection) => (
            <div
              key={connection.id}
              className="group relative flex flex-col p-4 border rounded-xl bg-card hover:shadow-md transition-all duration-300"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-primary" />
                    <span className="font-medium">{connection.name}</span>
                    {getStatusIcon(connection.status)}
                  </div>
                  <code className="text-xs px-2 py-0.5 rounded-md bg-muted">
                    {connection.id}
                  </code>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive"
                  onClick={() => setConnectionToDelete(connection)}
                >
                  <Unplug className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex items-center gap-2 mt-3 pt-3 border-t">
                <Badge
                  variant={
                    connection.status.toUpperCase() === "ACTIVE" ? "default" :
                    connection.status.toUpperCase() === "ERROR" ? "destructive" :
                    "secondary"
                  }
                >
                  {connection.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Created by: {connection.created_by_email}
                </span>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>

      <Dialog
        open={!!connectionToDelete}
        onOpenChange={(open) => !open && setConnectionToDelete(null)}
      >
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              Disconnect Connection
            </DialogTitle>
            <DialogDescription className="pt-2">
              Are you sure you want to disconnect <span className="font-medium">{connectionToDelete?.name}</span>?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => setConnectionToDelete(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDisconnect}
            >
              Disconnect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
