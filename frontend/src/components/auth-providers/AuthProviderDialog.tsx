import React, { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ConfigureAuthProviderView } from "./ConfigureAuthProviderView";
import { AuthProviderDetailView } from "./AuthProviderDetailView";
import { EditAuthProviderView } from "@/components/shared/views/EditAuthProviderView";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";
import type { DialogViewProps } from "@/components/types/dialog";

export type { DialogViewProps };

interface AuthProviderDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    mode: 'auth-provider' | 'auth-provider-detail' | 'auth-provider-edit';
    authProvider: any;
    connection?: any;
    onComplete?: (result: any) => void;
}

export const AuthProviderDialog: React.FC<AuthProviderDialogProps> = ({
    open,
    onOpenChange,
    mode,
    authProvider,
    connection,
    onComplete
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const navigate = useNavigate();
    const [currentView, setCurrentView] = useState(mode);
    const [viewData, setViewData] = useState<Record<string, any>>({});

    // Update current view when mode changes
    useEffect(() => {
        setCurrentView(mode);

        // Set initial view data based on mode
        if (authProvider) {
            const initialData: Record<string, any> = {
                authProviderId: authProvider.short_name,
                authProviderName: authProvider.name,
                authProviderShortName: authProvider.short_name,
                dialogId: `auth-provider-${authProvider.short_name}`
            };

            if (connection) {
                initialData.authProviderConnectionId = connection.readable_id;
                initialData.authProviderConnectionName = connection.name;
            }

            setViewData(initialData);
        }
    }, [mode, authProvider, connection]);

    const handleCancel = () => {
        onOpenChange(false);
        if (onComplete) {
            onComplete({ cancelled: true });
        }
    };

    const handleError = (error: Error | string, errorSource?: string) => {
        console.error("Dialog error:", error, "from:", errorSource);

        // Close the dialog
        onOpenChange(false);

        // Redirect with error
        redirectWithError(navigate, {
            serviceName: errorSource || authProvider?.name || "Auth Provider",
            errorMessage: error instanceof Error ? error.message : String(error),
            dialogId: viewData.dialogId
        });
    };

    const handleNext = (data?: any) => {
        console.log("🚀 [AuthProviderDialog] handleNext called with:", data);

        // Merge new data with existing viewData
        const newViewData = { ...viewData, ...data };
        setViewData(newViewData);

        // If we have an authProviderConnectionId, switch to detail view
        if (data?.authProviderConnectionId) {
            setCurrentView('auth-provider-detail');
        }
    };

    const handleComplete = (result?: any) => {
        console.log("✅ [AuthProviderDialog] handleComplete called with:", result);

        // Handle different completion actions
        if (result?.action === 'edit') {
            // Switch to edit mode
            setCurrentView('auth-provider-edit');

            // Update view data with connection info
            const newViewData = {
                ...viewData,
                authProviderConnectionId: result.authProviderConnectionId,
                authProviderName: result.authProviderName,
                authProviderShortName: result.authProviderShortName
            };
            setViewData(newViewData);
        } else if (result?.action === 'updated') {
            // After successful update, go back to detail view
            setCurrentView('auth-provider-detail');

            // Update view data with new connection info
            const newViewData = {
                ...viewData,
                authProviderConnectionId: result.authProviderConnectionId
            };
            setViewData(newViewData);

            // Also notify parent
            if (onComplete) {
                onComplete(result);
            }
        } else {
            // For other actions (deleted, success), close the dialog
            onOpenChange(false);

            if (onComplete) {
                onComplete(result);
            }
        }
    };

    const renderView = () => {
        switch (currentView) {
            case 'auth-provider':
                return (
                    <ConfigureAuthProviderView
                        onNext={handleNext}
                        onCancel={handleCancel}
                        onComplete={handleComplete}
                        onError={handleError}
                        viewData={viewData}
                    />
                );

            case 'auth-provider-detail':
                return (
                    <AuthProviderDetailView
                        onCancel={handleCancel}
                        onComplete={handleComplete}
                        onError={handleError}
                        viewData={viewData}
                    />
                );

            case 'auth-provider-edit':
                return (
                    <EditAuthProviderView
                        onCancel={handleCancel}
                        onComplete={handleComplete}
                        onError={handleError}
                        viewData={viewData}
                    />
                );

            default:
                return null;
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className={cn(
                    "max-w-4xl max-h-[90vh] p-0 flex flex-col",
                    isDark ? "bg-card-solid border-border" : "bg-white"
                )}
            >
                {renderView()}
            </DialogContent>
        </Dialog>
    );
};

export default AuthProviderDialog;
