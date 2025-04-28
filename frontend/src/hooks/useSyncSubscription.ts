import { useEffect, useRef, useState } from "react";
import { env } from "../config/env";
import { apiClient } from "@/lib/api";

interface SyncUpdate {
  updated?: number;
  inserted?: number;
  deleted?: number;
  [key: string]: any;
}

export function useSyncSubscription(jobId?: string | null) {
  const [updates, setUpdates] = useState<SyncUpdate[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    // Create a cleanup function for when the component unmounts or jobId changes
    let isMounted = true;
    const cleanup = () => {
      if (eventSourceRef.current) {
        console.log("Closing sync subscription event source");
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

    // Async function to get the auth token and create the EventSource
    const setupEventSource = async () => {
      try {
        // Get the auth token from the API client
        const token = await apiClient.getToken();

        // Create the URL with the auth token as a query parameter
        const baseUrl = `${env.VITE_API_URL}/sync/job/${jobId}/subscribe`;
        const url = token
          ? `${baseUrl}?token=${encodeURIComponent(token)}`
          : baseUrl;

        console.log(`Creating sync subscription to: ${jobId}`);

        // Create and setup the EventSource
        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.onmessage = (event) => {
          if (!isMounted) return;

          try {
            const data: SyncUpdate = JSON.parse(event.data);
            setUpdates((prev) => [...prev, data]);
          } catch (err) {
            console.error("Failed to parse SSE data:", err);
          }
        };

        es.onerror = (error) => {
          console.error("Sync subscription failed:", error);
          es.close();
          eventSourceRef.current = null;
        };
      } catch (error) {
        console.error("Error setting up sync subscription:", error);
      }
    };

    // Set up the event source
    void setupEventSource();

    // Return cleanup function
    return () => {
      isMounted = false;
      cleanup();
    };
  }, [jobId]);

  return updates;
}
