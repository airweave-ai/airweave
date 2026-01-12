import { useCallback, useRef, useState, useEffect } from 'react';
import type {
  ChildToParentMessage,
  ParentToChildMessage,
  SessionStatus,
} from '../lib/types';

interface UseParentMessagingReturn {
  isConnected: boolean;
  requestToken: () => Promise<string | null>;
  notifyStatusChange: (status: SessionStatus) => void;
  notifyConnectionCreated: (connectionId: string) => void;
  requestClose: (reason: 'success' | 'cancel' | 'error') => void;
}

interface PendingRequest {
  resolve: (value: string | null) => void;
  reject: (error: Error) => void;
}

// Check if running in iframe (runs once at module load for SSR safety)
function isInIframe(): boolean {
  if (typeof window === 'undefined') return false;
  return window.parent !== window;
}

export function useParentMessaging(): UseParentMessagingReturn {
  // Initialize to true if we're in an iframe, since connection is instant
  const [isConnected, setIsConnected] = useState(() => isInIframe());
  const pendingRequests = useRef<Map<string, PendingRequest>>(new Map());
  const hasInitialized = useRef(false);

  // Helper to send messages to parent
  const sendToParent = useCallback((message: ChildToParentMessage) => {
    if (typeof window !== 'undefined' && window.parent !== window) {
      window.parent.postMessage(message, '*');
    }
  }, []);

  useEffect(() => {
    // Only run in browser
    if (typeof window === 'undefined') return;

    // Check if we're in an iframe
    if (window.parent === window) {
      console.warn('Not running in an iframe, parent messaging skipped');
      return;
    }

    const handleMessage = (event: MessageEvent<ParentToChildMessage>) => {
      // TODO: In production, validate event.origin against allowed origins
      const { data } = event;

      if (!data || typeof data !== 'object' || !('type' in data)) {
        return;
      }

      switch (data.type) {
        case 'TOKEN_RESPONSE': {
          const pending = pendingRequests.current.get(data.requestId);
          if (pending) {
            pending.resolve(data.token);
            pendingRequests.current.delete(data.requestId);
          }
          break;
        }
        case 'TOKEN_ERROR': {
          const pending = pendingRequests.current.get(data.requestId);
          if (pending) {
            pending.resolve(null);
            pendingRequests.current.delete(data.requestId);
          }
          break;
        }
      }
    };

    window.addEventListener('message', handleMessage);

    // Signal ready to parent (only once)
    if (!hasInitialized.current) {
      hasInitialized.current = true;
      sendToParent({ type: 'CONNECT_READY' });
    }

    return () => {
      window.removeEventListener('message', handleMessage);
      setIsConnected(false);
    };
  }, [sendToParent]);

  const requestToken = useCallback(async (): Promise<string | null> => {
    if (typeof window === 'undefined' || window.parent === window) {
      return null;
    }

    const requestId = crypto.randomUUID();

    return new Promise<string | null>((resolve, reject) => {
      pendingRequests.current.set(requestId, { resolve, reject });

      sendToParent({ type: 'REQUEST_TOKEN', requestId });

      // Timeout after 10 seconds
      setTimeout(() => {
        if (pendingRequests.current.has(requestId)) {
          pendingRequests.current.delete(requestId);
          resolve(null);
        }
      }, 10000);
    });
  }, [sendToParent]);

  const notifyStatusChange = useCallback(
    (status: SessionStatus) => {
      sendToParent({ type: 'STATUS_CHANGE', status });
    },
    [sendToParent]
  );

  const notifyConnectionCreated = useCallback(
    (connectionId: string) => {
      sendToParent({ type: 'CONNECTION_CREATED', connectionId });
    },
    [sendToParent]
  );

  const requestClose = useCallback(
    (reason: 'success' | 'cancel' | 'error') => {
      sendToParent({ type: 'CLOSE', reason });
    },
    [sendToParent]
  );

  return {
    isConnected,
    requestToken,
    notifyStatusChange,
    notifyConnectionCreated,
    requestClose,
  };
}
