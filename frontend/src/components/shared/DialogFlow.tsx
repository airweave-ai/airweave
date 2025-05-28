import React, { useState, useEffect, useRef } from "react";
import { Dialog, DialogContent, DialogPortal, DialogOverlay } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { CreateCollectionView } from "./views/CreateCollectionView";
import { SourceSelectorView } from "./views/SourceSelectorView";
import { ConfigureSourceView } from "./views/ConfigureSourceView";
import { useNavigate, useSearchParams } from "react-router-dom";
import { redirectWithError, getStoredErrorDetails, clearStoredErrorDetails, CONNECTION_ERROR_STORAGE_KEY } from "@/lib/error-utils";
import { ConnectionErrorView } from "./views/ConnectionErrorView";

// Flow types
export type DialogFlowMode =
    | "source-button"     // Dashboard SourceButton flow
    | "add-source"        // CollectionDetailView "+ add source" flow
    | "create-collection"; // DashboardLayout "+ create collection" flow

interface DialogFlowProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    mode: DialogFlowMode;
    sourceId?: string;
    sourceName?: string;
    sourceShortName?: string;
    collectionId?: string;
    collectionName?: string;
    onComplete?: (result: any) => void;
    dialogId?: string; // Add unique dialog ID prop
    errorData?: any; // Add explicit error data prop for direct error passing
}

// Add this interface after DialogFlowProps
export interface DialogViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: Record<string, any>;
    onError?: (error: Error | string, errorSource?: string) => void;
}

export const DialogFlow: React.FC<DialogFlowProps> = ({
    isOpen,
    onOpenChange,
    mode,
    sourceId,
    sourceName,
    sourceShortName,
    collectionId,
    collectionName,
    onComplete,
    dialogId = "default", // Default ID if none provided
    errorData,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const [currentStep, setCurrentStep] = useState(0);
    const [viewData, setViewData] = useState<Record<string, any>>({});
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [showErrorView, setShowErrorView] = useState(false);
    const [errorViewData, setErrorViewData] = useState<any>(null);
    const [hasBeenForced, setHasBeenForced] = useState(false);

    // Add a ref to track if we've already processed restore
    const hasProcessedRestoreRef = useRef(false);
    // Add a new ref to track if dialog is being restored without reset
    const isRestoringRef = useRef(false);

    // Reset state when dialog opens or mode changes
    useEffect(() => {
        // DON'T reset viewData or currentStep if we're restoring dialog or in restoration process
        if (isOpen && !hasProcessedRestoreRef.current && !isRestoringRef.current) {
            setCurrentStep(0);
            setViewData({
                sourceId,
                sourceName,
                sourceShortName,
                collectionId,
                collectionName,
                dialogId
            });
        }
    }, [isOpen, mode, sourceId, sourceName, sourceShortName, collectionId, collectionName, dialogId]);

    // Handle direct error data passed via props
    useEffect(() => {
        if (errorData && isOpen) {
            console.log("🔔 [DialogFlow] Direct error data provided:", errorData);
            setErrorViewData({
                serviceName: errorData.serviceName || sourceName || "the service",
                sourceShortName: errorData.sourceShortName || sourceShortName || viewData.sourceShortName || "unknown",
                errorMessage: errorData.errorMessage || "Connection failed",
                errorDetails: errorData.errorDetails,
                retryAction: errorData.retryAction
            });
            setShowErrorView(true);
        }
    }, [errorData, isOpen, sourceName, sourceShortName, viewData]);

    // SINGLE error handling and dialog restoration effect
    useEffect(() => {
        const restoreDialog = searchParams.get('restore_dialog') === 'true';
        const oauthError = searchParams.get('oauth_error') === 'true';
        const connectionError = searchParams.get('connected') === 'error';

        // Handle dialog restoration
        if ((restoreDialog || oauthError) && !hasProcessedRestoreRef.current) {
            isRestoringRef.current = true;

            const newUrl = window.location.pathname;
            window.history.replaceState({}, '', newUrl);

            const savedStateJson = sessionStorage.getItem('oauth_dialog_state');
            if (savedStateJson) {
                try {
                    const savedState = JSON.parse(savedStateJson);
                    console.log("🔄 Restoring dialog state:", savedState);
                    console.log("⚠️ Important values:", {
                        credentialId: savedState.credentialId,
                        isAuthenticated: savedState.isAuthenticated,
                        currentStep: savedState.currentStep,
                        dialogFlowStep: savedState.dialogFlowStep,
                        dialogId: savedState.dialogId
                    });

                    if (savedState.dialogId && savedState.dialogId === dialogId) {
                        console.log(`🎯 Dialog ID match: ${dialogId}, restoring this dialog instance`);

                        const restoredStep = typeof savedState.dialogFlowStep === 'number' ? savedState.dialogFlowStep : 1;
                        setCurrentStep(restoredStep);
                        console.log(`🔢 Setting current step to: ${restoredStep}`);

                        setViewData({
                            ...savedState,
                            dialogId: savedState.dialogId,
                            dialogFlowStep: restoredStep,
                            dialogMode: savedState.dialogMode || mode
                        });

                        setTimeout(() => {
                            console.log(`🚨 Forcing dialog open with dialogId: ${dialogId}`);
                            setHasBeenForced(true);
                            hasProcessedRestoreRef.current = true;
                            onOpenChange(true);
                            sessionStorage.removeItem('oauth_dialog_state');

                            setTimeout(() => {
                                isRestoringRef.current = false;
                                console.log(`✅ Restoration complete for dialog: ${dialogId}`);
                            }, 50);
                        }, 50);
                    } else {
                        console.log(`⏭️ Dialog ID mismatch: saved=${savedState.dialogId}, current=${dialogId}, skipping restore`);
                        isRestoringRef.current = false;
                    }

                    console.log("📊 FULL SAVED STATE IN DIALOG FLOW:", JSON.stringify(savedState, null, 2));
                    console.log("📊 FULL VIEW DATA AFTER RESTORE:", JSON.stringify(viewData, null, 2));
                } catch (error) {
                    console.error("❌ Error restoring dialog state:", error);
                    isRestoringRef.current = false;

                    setErrorViewData({
                        serviceName: sourceName || "Dialog",
                        sourceShortName: sourceShortName || "dialog",
                        errorMessage: "Failed to restore dialog state",
                        errorDetails: error instanceof Error ? error.stack : String(error)
                    });
                    setShowErrorView(true);
                    onOpenChange(true);
                }
            } else {
                isRestoringRef.current = false;
            }
        }
        // Handle connection errors - ONLY for the matching dialogId
        else if (connectionError) {
            console.log("🔍 Checking for stored error details");
            const errorDetails = getStoredErrorDetails();

            if (errorDetails) {
                console.log("🔔 Found error details in localStorage:",
                    { type: typeof errorDetails, hasMessage: !!errorDetails.errorMessage });

                // ONLY open THIS dialog if the error was meant for it
                if (dialogId && errorDetails.dialogId === dialogId) {
                    const errorMessage = errorDetails.errorMessage || "Connection failed";
                    let errorDetailsText = errorDetails.errorDetails || "";

                    if (errorMessage && typeof errorMessage === 'string' && errorMessage.includes('{')) {
                        try {
                            const jsonStart = errorMessage.indexOf('{');
                            const jsonEnd = errorMessage.lastIndexOf('}') + 1;
                            if (jsonStart > -1 && jsonEnd > jsonStart) {
                                const jsonStr = errorMessage.substring(jsonStart, jsonEnd);
                                const parsed = JSON.parse(jsonStr);
                                if (parsed.detail) {
                                    errorDetailsText = parsed.detail;
                                }
                            }
                        } catch (e) {
                            console.error("Error parsing JSON from error message:", e);
                        }
                    }

                    setErrorViewData({
                        serviceName: errorDetails.serviceName || sourceName || "the service",
                        sourceShortName: errorDetails.sourceShortName ||
                            sourceShortName ||
                            viewData.sourceShortName ||
                            "unknown",
                        errorMessage: errorMessage,
                        errorDetails: errorDetailsText,
                        retryAction: errorDetails.canRetry ? () => {
                            setShowErrorView(false);
                            if (errorDetails.dialogState?.dialogFlowStep) {
                                setCurrentStep(errorDetails.dialogState.dialogFlowStep);
                            }
                        } : undefined
                    });

                    setShowErrorView(true);
                    onOpenChange(true);

                    setTimeout(() => {
                        if (isOpen && showErrorView) {
                            const newUrl = window.location.pathname;
                            window.history.replaceState({}, '', newUrl);
                        }
                    }, 500);
                }
            }

            // Clean up URL regardless
            setTimeout(() => {
                const newUrl = window.location.pathname;
                window.history.replaceState({}, '', newUrl);
            }, 100);
        }
    }, [searchParams, onOpenChange, isOpen, dialogId, mode, sourceName, sourceShortName, showErrorView]);

    // Add a direct effect on isOpen to log when it changes
    useEffect(() => {
        console.log(`🔍 Dialog isOpen changed for dialogId=${dialogId}: ${isOpen}`);

        // If dialog was open and is now closing (not due to OAuth transition)
        if (!isOpen && hasBeenForced) {
            // Call handleCancel to properly clean up state
            handleCancel();
        }
    }, [isOpen, dialogId, hasBeenForced]);

    // Define flow sequences based on mode
    const flowSequences = {
        "source-button": ["createCollection", "connectSource"],
        "add-source": ["sourceSelector", "connectSource"],
        "create-collection": ["sourceSelector", "createCollection", "connectSource"]
    };

    // Get current flow sequence
    const currentFlow = flowSequences[mode as keyof typeof flowSequences];
    const currentView = showErrorView ? "error" : (currentFlow ? currentFlow[currentStep] : null);

    // Effect for opening dialog with populated credential info
    useEffect(() => {
        if (viewData.credentialId && !isOpen && hasProcessedRestoreRef.current && !viewData.isCompleted) {
            console.log(`🔔 Opening dialog ${dialogId} with populated viewData:`, JSON.stringify(viewData, null, 2));
            onOpenChange(true);
        }
    }, [viewData, isOpen, onOpenChange, dialogId]);

    // Effect for resetting authentication
    useEffect(() => {
        if (viewData.isAuthenticated && !viewData.credentialId) {
            setViewData(prevData => ({
                ...prevData,
                isAuthenticated: false
            }));
        }
    }, [viewData.isAuthenticated]);

    // Effect for handling dialog closing
    useEffect(() => {
        if (!isOpen && hasProcessedRestoreRef.current) {
            console.log('🚪 Dialog closed, cleaning up state');
            hasProcessedRestoreRef.current = false;
            isRestoringRef.current = false;

            if (showErrorView) {
                setShowErrorView(false);
                setErrorViewData(null);
            }
        }
    }, [isOpen, showErrorView]);

    // Render view function
    const renderView = () => {
        if (showErrorView || currentView === "error") {
            return (
                <ConnectionErrorView
                    onCancel={() => {
                        setShowErrorView(false);
                        onOpenChange(false);

                        setTimeout(() => {
                            clearStoredErrorDetails();
                            const url = new URL(window.location.href);
                            if (url.searchParams.has('connected')) {
                                url.searchParams.delete('connected');
                                window.history.replaceState({}, '', url.toString());
                            }
                        }, 100);
                    }}
                    viewData={errorViewData}
                />
            );
        }

        if (currentView === null) {
            return (
                <ConnectionErrorView
                    onCancel={() => {
                        onOpenChange(false);
                    }}
                    viewData={{
                        serviceName: "Dialog Flow",
                        sourceShortName: "dialog",
                        errorMessage: `Configuration error in dialog flow`,
                        errorDetails: `Invalid mode: ${mode} or missing flow sequence`
                    }}
                />
            );
        }

        const commonProps = {
            onNext: handleNext,
            onCancel: handleCancel,
            onComplete: handleComplete,
            viewData: {
                ...viewData,
                dialogId,
                dialogFlowStep: currentStep,
                dialogMode: mode,
            } as any,
            onError: handleError,
        };

        if (currentStep > 0) {
            (commonProps as any).onBack = handleBack;
        }

        switch (currentView) {
            case "sourceSelector":
                return <SourceSelectorView {...commonProps} />;
            case "createCollection":
                return <CreateCollectionView {...commonProps} />;
            case "connectSource":
                return <ConfigureSourceView {...commonProps} />;
            default:
                return (
                    <ConnectionErrorView
                        onCancel={() => onOpenChange(false)}
                        viewData={{
                            serviceName: "Dialog Flow",
                            sourceShortName: "dialog",
                            errorMessage: `Unknown view: ${currentView}`,
                            errorDetails: `Available views: sourceSelector, createCollection, connectSource`
                        }}
                    />
                );
        }
    };

    // Handle next step
    const handleNext = (data?: any) => {
        if (data) {
            setViewData(prevData => {
                const newData = {
                    ...prevData,
                    ...data,
                    dialogId,
                    dialogMode: mode
                };
                return newData;
            });
        }

        if (currentStep < currentFlow.length - 1) {
            setCurrentStep(prevStep => prevStep + 1);
        }
    };

    // Handle back step
    const handleBack = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
        }
    };

    // Handle cancel
    const handleCancel = () => {
        console.log('🚪 Cancelling dialog with ID:', dialogId);

        const isInErrorMode = showErrorView;

        // Always close the dialog immediately
        onOpenChange(false);

        // Reset the dialog state
        setCurrentStep(0);
        setShowErrorView(false);
        setErrorViewData(null);

        // Clear credential data to prevent auto-reopening
        setViewData(prevData => ({
            sourceId,
            sourceName,
            sourceShortName,
            collectionId,
            collectionName,
            dialogId,
            credentialId: undefined,
            isAuthenticated: false
        }));

        // Clear error state from localStorage (if we were showing an error)
        if (isInErrorMode) {
            clearStoredErrorDetails();

            const currentUrl = new URL(window.location.href);
            if (currentUrl.searchParams.has('connected')) {
                currentUrl.searchParams.delete('connected');
                window.history.replaceState({}, '', currentUrl.toString());
            }
        }
    };

    // Handle completion
    const handleComplete = (result: any) => {
        if (result && result.isCompleted) {
            setViewData(prevData => ({
                ...prevData,
                isCompleted: true
            }));
        }

        onOpenChange(false);
        if (onComplete) {
            onComplete(result);
        }
    };

    // Add enhanced error handling function that can be passed to views
    const handleError = (error: Error | string, errorSource?: string) => {
        console.error(`❌ [DialogFlow] Error with dialogId=${dialogId}:`, error);

        // Create the ability to retry by default
        const canRetry = currentStep > 0;

        // First, close the dialog to prevent stale state
        onOpenChange(false);

        // Add the retry capability to the error data
        const errorMsg = error instanceof Error ? error.message : error;
        const errorStack = error instanceof Error ? error.stack : undefined;

        // Create complete error details
        const completeError = {
            serviceName: errorSource || viewData.sourceName || "the service",
            sourceShortName: viewData.sourceShortName || sourceShortName || "unknown",
            errorMessage: errorMsg,
            errorDetails: errorStack,
            canRetry,
            // Store current dialog state for potential retry
            dialogState: {
                ...viewData,
                dialogFlowStep: currentStep
            },
            dialogId,
            timestamp: Date.now()
        };

        // Use the common error utility to redirect with full details
        redirectWithError(navigate, completeError, errorSource || viewData.sourceName);
    };

    return (
        <Dialog
            open={isOpen}
            onOpenChange={(open) => {
                if (!open) {
                    handleCancel();
                } else {
                    onOpenChange(open);
                }
            }}
        >
            <DialogPortal>
                <DialogOverlay className="bg-black/75" />
                <DialogContent
                    className={cn(
                        "p-0 rounded-xl border overflow-hidden",
                        isDark ? "bg-background border-gray-800" : "bg-background border-gray-200"
                    )}
                    style={{
                        width: "800px",
                        height: "80vh",
                        maxWidth: "95vw",
                        maxHeight: "95vh"
                    }}
                >
                    <div className="h-full w-full overflow-hidden">
                        {renderView()}
                    </div>
                </DialogContent>
            </DialogPortal>
        </Dialog>
    );
};

export default DialogFlow;
