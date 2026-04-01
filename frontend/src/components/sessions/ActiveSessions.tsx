import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { SessionCard } from "./SessionCard";
import type { UserSession, SessionTerminationResult } from "@/types";

export function ActiveSessions() {
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [terminatingId, setTerminatingId] = useState<string | null>(null);
  const [isTerminatingAll, setIsTerminatingAll] = useState(false);

  const fetchSessions = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await apiClient.get("/users/me/sessions", { signal });
      if (signal?.aborted) return;
      if (response.ok) {
        setSessions(await response.json());
      }
    } catch (error) {
      if (signal?.aborted) return;
      console.error("Failed to fetch sessions:", error instanceof Error ? error.message : "unknown");
      toast.error("Failed to load sessions");
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchSessions(controller.signal);
    return () => controller.abort();
  }, [fetchSessions]);

  const handleTerminate = async (sessionId: string) => {
    setTerminatingId(sessionId);
    try {
      const response = await apiClient.delete(`/users/me/sessions/${sessionId}`);
      if (response.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        toast.success("Session terminated");
      } else {
        const data = await response.json();
        toast.error(data.detail || "Failed to terminate session");
      }
    } catch (error) {
      toast.error("Failed to terminate session");
    } finally {
      setTerminatingId(null);
    }
  };

  const handleTerminateAll = async () => {
    setIsTerminatingAll(true);
    try {
      const response = await apiClient.delete("/users/me/sessions");
      if (response.ok) {
        const result: SessionTerminationResult = await response.json();
        setSessions((prev) => prev.filter((s) => s.is_current));
        toast.success(`Terminated ${result.terminated_count} session(s)`);
      } else {
        const data = await response.json();
        toast.error(data.detail || "Failed to terminate sessions");
      }
    } catch (error) {
      toast.error("Failed to terminate sessions");
    } finally {
      setIsTerminatingAll(false);
    }
  };

  const otherSessions = sessions.filter((s) => !s.is_current);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>Loading sessions...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Active Sessions</CardTitle>
            <CardDescription>
              Devices where you are currently signed in
            </CardDescription>
          </div>
          {otherSessions.length > 0 && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isTerminatingAll}
                >
                  {isTerminatingAll ? "Signing out..." : "Sign out all other devices"}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Sign out all other devices?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will terminate all sessions except your current one.
                    You will need to sign in again on those devices.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleTerminateAll}>
                    Sign out all
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active sessions</p>
        ) : (
          sessions.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              onTerminate={handleTerminate}
              isTerminating={terminatingId === session.id}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
