import { createStore } from 'zustand/vanilla';

export interface RequestContext {
  organizationId: string | null;
}

const defaultRequestContext: RequestContext = {
  organizationId: null,
};

interface RequestContextStoreState {
  currentRequestContext: RequestContext;
  resetCurrentRequestContext: () => void;
  setCurrentOrganizationId: (organizationId: string | null) => void;
  setCurrentRequestContext: (requestContext: RequestContext) => void;
}

export const requestContextStore = createStore<RequestContextStoreState>()(
  (set) => ({
    currentRequestContext: defaultRequestContext,
    resetCurrentRequestContext: () => {
      set({ currentRequestContext: defaultRequestContext });
    },
    setCurrentOrganizationId: (organizationId) => {
      set({ currentRequestContext: { organizationId } });
    },
    setCurrentRequestContext: (requestContext) => {
      set({ currentRequestContext: requestContext });
    },
  }),
);

export function getCurrentRequestContext() {
  return requestContextStore.getState().currentRequestContext;
}

export function setCurrentRequestContext(requestContext: RequestContext) {
  requestContextStore.getState().setCurrentRequestContext(requestContext);
}

export function resetCurrentRequestContext() {
  requestContextStore.getState().resetCurrentRequestContext();
}
