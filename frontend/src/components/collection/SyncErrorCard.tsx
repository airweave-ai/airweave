import { AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { DESIGN_SYSTEM } from "@/lib/design-system";

export interface SyncErrorCardProps {
    error: string;
    isDark: boolean;
}

export const SyncErrorCard = ({
    error,
    isDark
}: SyncErrorCardProps) => {
    return (
        <Card className={cn(
            "overflow-hidden border p-0",
            DESIGN_SYSTEM.radius.card,
            isDark
                ? "border-red-800/10 bg-transparent"
                : "border-gray-200 bg-white"
        )}>
            <CardHeader className={cn(DESIGN_SYSTEM.spacing.padding.compact, "pb-0")}>
                <h3 className={cn(
                    DESIGN_SYSTEM.typography.sizes.title,
                    DESIGN_SYSTEM.typography.weights.medium,
                    "flex items-center",
                    isDark ? "text-red-400/80" : "text-red-500/90"
                )}>
                    <AlertCircle className={cn(DESIGN_SYSTEM.icons.button, "mr-2 stroke-[2.5px]")} />
                    Sync Error
                </h3>
            </CardHeader>
            <CardContent className={DESIGN_SYSTEM.spacing.padding.compact}>
                <div className={cn(
                    DESIGN_SYSTEM.spacing.padding.default,
                    DESIGN_SYSTEM.radius.button,
                    "font-mono whitespace-pre-wrap overflow-auto max-h-48",
                    DESIGN_SYSTEM.typography.sizes.body,
                    isDark
                        ? "bg-gray-800/50 text-gray-200 border border-gray-700"
                        : "bg-gray-50 text-gray-700 border border-gray-200"
                )}>
                    {error}
                </div>
                <p className={cn(
                    DESIGN_SYSTEM.typography.sizes.header,
                    "mt-3 flex items-center",
                    isDark ? "text-gray-400" : "text-gray-500"
                )}>
                    Please fix the error and try running the sync again.
                </p>
            </CardContent>
        </Card>
    );
};
