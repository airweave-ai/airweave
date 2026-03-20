import { Button } from "@/components/ui/button";
import { Plus, Check } from "lucide-react";
import { getAuthProviderIconUrl, getColorClass } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useImageFallback } from "@/hooks/use-image-fallback";

interface AuthProviderButtonProps {
    id: string;
    name: string;
    shortName: string;
    isConnected?: boolean;
    connectionCount?: number;
    isComingSoon?: boolean;
    onClick?: () => void;
}

export const AuthProviderButton = ({
    id,
    name,
    shortName,
    isConnected = false,
    connectionCount = 0,
    isComingSoon = false,
    onClick
}: AuthProviderButtonProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    // Log when button is clicked
    const handleClick = () => {
        // Don't handle clicks for coming soon providers
        if (isComingSoon) return;

        console.log('🔘 [AuthProviderButton] Button clicked:', {
            id,
            name,
            shortName,
            isConnected
        });
        if (onClick) {
            onClick();
        }
    };

    const iconSrc = getAuthProviderIconUrl(shortName, resolvedTheme);
    const { error: iconError, onError: onIconError } = useImageFallback(iconSrc);

    return (
        <div
            className={cn(
                "border rounded-lg overflow-hidden transition-all min-w-[150px] relative",
                isComingSoon
                    ? "cursor-not-allowed opacity-60"
                    : "cursor-pointer group",
                isDark
                    ? "border-gray-800 hover:border-gray-700 bg-gray-900/50 hover:bg-gray-900"
                    : "border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50",
                isComingSoon && "hover:border-gray-800 hover:bg-gray-900/50" // Disable hover effects for coming soon
            )}
            onClick={handleClick}
        >
            <div className="p-2 sm:p-3 md:p-4 flex items-center justify-between">
                <div className="flex items-center gap-2 sm:gap-3">
                    <div className={cn(
                        "flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 md:w-10 md:h-10 overflow-hidden rounded-md flex-shrink-0",
                        iconError && getColorClass(shortName)
                    )}>
                        {iconError ? (
                            <span className="text-white font-semibold text-xs sm:text-sm">
                                {shortName.substring(0, 2).toUpperCase()}
                            </span>
                        ) : (
                            <img
                                src={iconSrc}
                                alt={`${shortName} icon`}
                                className="w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 object-contain"
                                onError={onIconError}
                            />
                        )}
                    </div>
                    <div className="flex flex-col">
                        <div className="flex items-center gap-1.5">
                            <span className="text-xs sm:text-sm font-medium truncate">{name}</span>
                            {connectionCount > 1 && (
                                <span className={cn(
                                    "text-[10px] font-medium px-1.5 py-0.5 rounded-full",
                                    isDark
                                        ? "bg-blue-900/60 text-blue-300"
                                        : "bg-blue-100 text-blue-700"
                                )}>
                                    {connectionCount}
                                </span>
                            )}
                        </div>
                        {isComingSoon && (
                            <span className="text-[10px] sm:text-xs text-muted-foreground">
                                Coming soon
                            </span>
                        )}
                    </div>
                </div>
                {!isComingSoon && (
                    <Button
                        size="icon"
                        variant="ghost"
                        className={cn(
                            "h-6 w-6 sm:h-7 sm:w-7 md:h-8 md:w-8 rounded-full flex-shrink-0",
                            isConnected
                                ? isDark
                                    ? "bg-green-900/80 text-green-400 hover:bg-green-800/80 hover:text-green-300 group-hover:bg-green-800"
                                    : "bg-green-100/80 text-green-600 hover:bg-green-200 hover:text-green-700 group-hover:bg-green-200/80"
                                : isDark
                                    ? "bg-gray-800/80 text-blue-400 hover:bg-blue-600/20 hover:text-blue-300 group-hover:bg-blue-600/30"
                                    : "bg-gray-100/80 text-blue-500 hover:bg-blue-100 hover:text-blue-600 group-hover:bg-blue-100/80"
                        )}
                    >
                        {isConnected ? (
                            <Check className="h-3 w-3 sm:h-3.5 sm:w-3.5 md:h-4 md:w-4" />
                        ) : (
                            <Plus className="h-3 w-3 sm:h-3.5 sm:w-3.5 md:h-4 md:w-4 group-hover:h-4 group-hover:w-4 sm:group-hover:h-4.5 sm:group-hover:w-4.5 md:group-hover:h-5 md:group-hover:w-5 transition-all" />
                        )}
                    </Button>
                )}
            </div>
        </div>
    );
};

export default AuthProviderButton;
