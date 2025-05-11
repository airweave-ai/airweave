import { env } from '../config/env';

// Define a token provider interface
interface TokenProvider {
  getToken: () => Promise<string | null>;
  clearToken?: () => void;
  isReady?: () => boolean;
}

// Default implementation that uses env variable
const defaultTokenProvider: TokenProvider = {
  getToken: async () => env.VITE_ACCESS_TOKEN || null,
  clearToken: () => {
    console.log('Default clearToken called - no effect in default provider');
  },
  isReady: () => true,
};

// Current token provider instance
let tokenProvider: TokenProvider = defaultTokenProvider;

// Request queue system
interface QueuedRequest {
  execute: () => Promise<Response>;
  resolve: (value: Response) => void;
  reject: (reason: any) => void;
}

const requestQueue: QueuedRequest[] = [];
let isProcessingQueue = false;

// Function to set a custom token provider
export const setTokenProvider = (provider: TokenProvider) => {
  tokenProvider = provider;

  // Try to process any queued requests when provider changes
  processQueue();
};

// Process the request queue
const processQueue = async () => {
  // If we're already processing or the queue is empty, do nothing
  if (isProcessingQueue || requestQueue.length === 0) {
    return;
  }

  // Check if auth is ready
  const isAuthReady = tokenProvider.isReady ? tokenProvider.isReady() : true;
  if (!isAuthReady) {
    // Auth not ready yet, try again later
    setTimeout(processQueue, 100);
    return;
  }

  isProcessingQueue = true;

  console.log(`Processing request queue: ${requestQueue.length} requests`);

  while (requestQueue.length > 0) {
    const request = requestQueue.shift();
    if (!request) continue;

    try {
      const response = await request.execute();
      request.resolve(response);
    } catch (error) {
      request.reject(error);
    }
  }

  isProcessingQueue = false;
};

// Helper to queue a request if auth is not ready
const queueOrExecute = async (requestFn: () => Promise<Response>): Promise<Response> => {
  const isAuthReady = tokenProvider.isReady ? tokenProvider.isReady() : true;

  if (isAuthReady) {
    return requestFn();
  }

  // Queue the request
  return new Promise((resolve, reject) => {
    console.log('Queueing request until auth is ready');
    requestQueue.push({
      execute: requestFn,
      resolve,
      reject,
    });
  });
};

export const API_CONFIG = {
  baseURL: env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
} as const;

type ApiResponse<T = any> = Promise<Response>;
type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

// Shared HTTP request function to eliminate duplication
const makeRequest = async <T>(
  method: HttpMethod,
  endpoint: string,
  options?: {
    data?: any;
    params?: Record<string, any>;
  }
): ApiResponse<T> => {
  const requestFn = async () => {
    const url = new URL(`${API_CONFIG.baseURL}${endpoint}`);
    if (options?.params) {
      Object.entries(options.params).forEach(([key, value]) =>
        url.searchParams.append(key, String(value))
      );
    }

    let token = await tokenProvider.getToken();
    const headers = {
      ...API_CONFIG.headers,
      ...(token && { Authorization: `Bearer ${token}` }),
    };

    const fetchOptions: RequestInit = {
      method,
      headers,
    };

    // Add body for methods that support it
    if (options?.data && method !== 'GET' && method !== 'DELETE') {
      fetchOptions.body = JSON.stringify(options.data);
    }

    let response = await fetch(url.toString(), fetchOptions);

    // Handle 401/403 by attempting token refresh once
    if ((response.status === 401 || response.status === 403) && tokenProvider.clearToken) {
      console.log(`Got ${response.status} error, attempting token refresh`);
      tokenProvider.clearToken(); // Clear the cached token
      token = await tokenProvider.getToken(); // Get a fresh token

      if (token) {
        console.log('Retrying request with fresh token');
        // Retry with new token
        const retryHeaders = {
          ...API_CONFIG.headers,
          Authorization: `Bearer ${token}`,
        };

        fetchOptions.headers = retryHeaders;
        response = await fetch(url.toString(), fetchOptions);
      }
    }

    return response;
  };

  return queueOrExecute(requestFn);
};

export const apiClient = {
  clearToken: () => {
    if (tokenProvider.clearToken) {
      tokenProvider.clearToken();
    } else {
      console.warn('No clearToken method available in current tokenProvider');
    }
  },

  // Add getToken method to get current auth token
  getToken: async (): Promise<string | null> => {
    return tokenProvider.getToken();
  },

  async get<T>(endpoint: string, params?: Record<string, any>): ApiResponse<T> {
    return makeRequest<T>('GET', endpoint, { params });
  },

  async post<T>(endpoint: string, data?: any, params?: Record<string, any>): ApiResponse<T> {
    return makeRequest<T>('POST', endpoint, { data, params });
  },

  async put<T>(endpoint: string, params?: Record<string, any>, data?: any): ApiResponse<T> {
    return makeRequest<T>('PUT', endpoint, { data, params });
  },

  async patch<T>(endpoint: string, data?: any, params?: Record<string, any>): ApiResponse<T> {
    return makeRequest<T>('PATCH', endpoint, { data, params });
  },

  async delete<T>(endpoint: string, params?: Record<string, any>): ApiResponse<T> {
    return makeRequest<T>('DELETE', endpoint, { params });
  },
};
