// Common types for dialog views
export type DialogViewProps = {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    onError?: (error: Error | string, errorSource?: string) => void;
    viewData?: Record<string, any>;
};
