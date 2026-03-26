import React from "react";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { format } from "date-fns";

interface AuthProviderConnectionsListProps {
    authProvider: any;
    onSelectConnection: (connection: any) => void;
    onAddNew: () => void;
    onCancel: () => void;
}

export const AuthProviderConnectionsList: React.FC<AuthProviderConnectionsListProps> = ({
    authProvider,
    onSelectConnection,
    onAddNew,
    onCancel,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const { authProviderConnections } = useAuthProvidersStore();

    const connections = authProviderConnections.filter(
        (conn) => conn.short_name === authProvider?.short_name
    );

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-md overflow-hidden flex items-center justify-center">
                    <img
                        src={getAuthProviderIconUrl(authProvider?.short_name, resolvedTheme)}
                        alt={`${authProvider?.name} icon`}
                        className="w-9 h-9 object-contain"
                    />
                </div>
                <div>
                    <h2 className="text-lg font-semibold">{authProvider?.name}</h2>
                    <p className="text-sm text-muted-foreground">
                        {connections.length} connection{connections.length !== 1 ? "s" : ""}
                    </p>
                </div>
            </div>

            {/* Connections list */}
            <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                {connections.map((conn) => (
                    <button
                        key={conn.readable_id}
                        onClick={() => onSelectConnection(conn)}
                        className={cn(
                            "w-full text-left p-4 rounded-lg border transition-colors",
                            isDark
                                ? "border-gray-800 hover:border-gray-700 hover:bg-gray-900/50"
                                : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                        )}
                    >
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium">{conn.name || conn.readable_id}</p>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    {conn.readable_id}
                                </p>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {conn.created_at
                                    ? format(new Date(conn.created_at), "MMM d, yyyy")
                                    : ""}
                            </p>
                        </div>
                    </button>
                ))}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-2 border-t">
                <Button variant="ghost" size="sm" onClick={onCancel}>
                    Close
                </Button>
                <Button size="sm" onClick={onAddNew} className="gap-1.5">
                    <Plus className="h-4 w-4" />
                    Add new connection
                </Button>
            </div>
        </div>
    );
};
