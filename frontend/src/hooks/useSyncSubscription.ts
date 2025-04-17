import { useEffect, useRef, useState } from "react";
import { env } from "../config/env";

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

<<<<<<< HEAD
    const url = `http://localhost:8001/sync/job/${jobId}/subscribe`; // make sure to use the correct URL
    const es = new EventSource(url, { withCredentials: true }); /* Add cleanup in useEffect return */
=======
    const url = `${env.VITE_API_URL}/sync/job/${jobId}/subscribe`;
    const es = new EventSource(url);
>>>>>>> upstream/main
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data: SyncUpdate = JSON.parse(event.data);
        setUpdates((prev) => prev.concat(data));
      } catch (err) {
        console.error("Failed to parse SSE data:", err);
      }
    };

    es.onerror = () => {
      console.error("Sync subscription failed. Closing connection.");
      es.close();
    };

    return () => {
      es.close();
    };
  }, [jobId]);

  return updates;
}
