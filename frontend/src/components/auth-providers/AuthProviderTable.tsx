import { useEffect, useState, useMemo } from "react";
import { AuthProviderButton } from "@/components/dashboard";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import { AuthProviderDialog } from "./AuthProviderDialog";
import { toast } from "sonner";

export const AuthProviderTable = () => {
    const { canManageOrganization } = useOrganizationContext();
    const canManage = canManageOrganization();
    // Use auth providers store
    const {
        authProviders,
        authProviderConnections,
        isLoading: isLoadingAuthProviders,
        isLoadingConnections,
        fetchAuthProviders,
        fetchAuthProviderConnections,
        isAuthProviderConnected,
        getConnectionForProvider
    } = useAuthProvidersStore();

    // Dialog state
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedAuthProvider, setSelectedAuthProvider] = useState<any>(null);
    const [selectedConnection, setSelectedConnection] = useState<any>(null);
    const [dialogMode, setDialogMode] = useState<'auth-provider' | 'auth-provider-detail' | 'auth-provider-edit' | 'auth-provider-list'>('auth-provider');
    const [remountKey, setRemountKey] = useState(0);

    // Fetch auth providers and connections on component mount
    useEffect(() => {
        // Fetch both auth providers and connections in parallel
        Promise.all([
            fetchAuthProviders(),
            fetchAuthProviderConnections()
        ]);
    }, [fetchAuthProviders, fetchAuthProviderConnections]);

    const handleAuthProviderClick = (authProvider: any) => {
        const connections = authProviderConnections.filter(conn => conn.short_name === authProvider.short_name);

        setSelectedAuthProvider(authProvider);

        if (connections.length === 0) {
            if (!canManage) {
                toast.info("Only admins can configure auth providers");
                return;
            }
            setSelectedConnection(null);
            setDialogMode('auth-provider');
            setDialogOpen(true);
        } else {
            setSelectedConnection(null);
            setDialogMode('auth-provider-list');
            setDialogOpen(true);
        }
    };

    const handleDialogComplete = (result: any) => {
        // Close the dialog
        setDialogOpen(false);

        // If it was an edit action, open edit dialog
        if (result?.action === 'edit') {

            // Store the auth provider details for edit dialog
            const tempAuthProvider = selectedAuthProvider;
            const tempConnection = selectedConnection;

            // Reset state first
            setSelectedAuthProvider(null);
            setSelectedConnection(null);
            setDialogMode('auth-provider');

            // After a small delay, set up and open edit dialog
            setTimeout(() => {
                setSelectedAuthProvider(tempAuthProvider);
                setSelectedConnection(tempConnection);
                setDialogMode('auth-provider-edit');
                setDialogOpen(true);
                setRemountKey(prev => prev + 1); // Force remount for clean state
            }, 100);

            return; // Don't refresh connections for edit action
        }

        // If it was an updated action, open detail dialog with refreshed data
        if (result?.action === 'updated') {

            // Find the updated connection from the refreshed list
            const updatedConnection = authProviderConnections.find(
                conn => conn.readable_id === result.authProviderConnectionId
            );

            if (updatedConnection && selectedAuthProvider) {
                // After a small delay, open detail dialog with updated data
                setTimeout(() => {
                    setSelectedAuthProvider(selectedAuthProvider);
                    setSelectedConnection(updatedConnection);
                    setDialogMode('auth-provider-detail');
                    setDialogOpen(true);
                    setRemountKey(prev => prev + 1); // Force remount for fresh data
                }, 100);
            }

            return; // Don't do default state reset
        }

        // If it was a deletion, increment remountKey to force dialog remount
        if (result?.action === 'deleted') {
            setRemountKey(prev => prev + 1);
        }

        // Reset state
        setSelectedAuthProvider(null);
        setSelectedConnection(null);
        setDialogMode('auth-provider');

        // Refresh connections if a new one was created or deleted
        if (result?.success) {
            fetchAuthProviderConnections();
        }
    };

    // Define coming soon providers
    const comingSoonProviders = [
        {
            id: 'coming-soon-klavis',
            name: 'Klavis',
            short_name: 'klavis',
            isComingSoon: true
        }
    ];

    // Combine real providers with coming soon providers
    const allProviders = useMemo(() => {
        return [...authProviders, ...comingSoonProviders];
    }, [authProviders]);

    // Memoize dialog key to prevent remounts
    const dialogKey = useMemo(() => {
        // Only use auth provider short name as key since connection ID isn't available when creating new
        return dialogOpen ? `auth-${selectedAuthProvider?.short_name || 'none'}-${remountKey}` : 'closed';
    }, [dialogOpen, selectedAuthProvider?.short_name, remountKey]);

    return (
        <div className="w-full">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {isLoadingAuthProviders || isLoadingConnections ? (
                    <div className="col-span-full flex justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"></div>
                    </div>
                ) : allProviders.length === 0 ? (
                    <div className="col-span-full text-center py-8 text-gray-500">
                        No auth providers available
                    </div>
                ) : (
                    allProviders.map(provider => {
                        const connections = authProviderConnections.filter(
                            conn => conn.short_name === provider.short_name
                        );

                        return (
                            <AuthProviderButton
                                key={provider.short_name}
                                id={provider.short_name}
                                name={provider.name}
                                shortName={provider.short_name}
                                isConnected={connections.length > 0}
                                connectionCount={connections.length}
                                isComingSoon={'isComingSoon' in provider ? provider.isComingSoon : false}
                                onClick={() => handleAuthProviderClick(provider)}
                            />
                        );
                    })
                )}
            </div>

            {/* Dialog for connecting to auth provider */}
            <AuthProviderDialog
                key={dialogKey}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                mode={dialogMode}
                authProvider={selectedAuthProvider}
                connection={selectedConnection}
                onComplete={handleDialogComplete}
            />
        </div>
    );
};
