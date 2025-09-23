import { create } from 'zustand';

export type PanelFlowType = 'addSource' | 'createCollection';
export type PanelViewType = 'sourceList' | 'collectionForm' | 'sourceConfig' | 'oauthRedirect';

interface PanelContext {
    collectionId?: string;
    collectionName?: string;
    sourceId?: string;
    sourceName?: string;
    sourceShortName?: string;
    authenticationUrl?: string;
    // Add other context as needed
}

interface SidePanelState {
    isOpen: boolean;
    flowType: PanelFlowType | null;
    currentView: PanelViewType | null;
    context: PanelContext;
    openPanel: (flowType: PanelFlowType, initialContext?: PanelContext) => void;
    closePanel: () => void;
    setView: (view: PanelViewType, newContext?: Partial<PanelContext>) => void;
}

export const useSidePanelStore = create<SidePanelState>((set, get) => ({
    isOpen: false,
    flowType: null,
    currentView: null,
    context: {},
    openPanel: (flowType, initialContext = {}) => {
        console.log(`[SidePanelStore] Opening panel for flow: ${flowType}`, initialContext);
        set({
            isOpen: true,
            flowType,
            currentView: flowType === 'createCollection' ? 'collectionForm' : 'sourceList',
            context: initialContext,
        });
    },
    closePanel: () => {
        console.log('[SidePanelStore] Closing panel');
        set({
            isOpen: false,
            flowType: null,
            currentView: null,
            context: {},
        });
    },
    setView: (view, newContext = {}) => {
        console.log(`[SidePanelStore] Setting view to: ${view}`, newContext);
        set(state => ({
            currentView: view,
            context: { ...state.context, ...newContext },
        }));
    },
}));
