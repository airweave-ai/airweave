import { Button } from "@/components/ui/button";
import { Plus, Check } from "lucide-react";
import { getAuthProviderIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";

interface AuthProviderButtonProps {
    id: string;
    name: string;
    shortName: string;
    isConnected?: boolean;
    isComingSoon?: boolean;  // Add this prop
    onClick?: () => void;
}

export const AuthProviderButton = ({
    id,
    name,
    shortName,
    isConnected = false,
    isComingSoon = false,  // Add default value
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

    // Get color class based on shortName for fallback
    const getColorClass = (shortName: string) => {
        const colors = [
            "bg-blue-500",
            "bg-green-500",
            "bg-purple-500",
            "bg-orange-500",
            "bg-pink-500",
            "bg-indigo-500",
            "bg-red-500",
            "bg-yellow-500",
        ];

        // Hash the short name to get a consistent color
        const index = shortName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
        return colors[index];
    };

    // Auth provider icon component
    const AuthProviderIcon = () => (
        <div className="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 md:w-10 md:h-10 overflow-hidden rounded-md flex-shrink-0">
            <img
                src={getAuthProviderIconUrl(shortName, resolvedTheme)}
                alt={`${shortName} icon`}
                className="w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 object-contain"
                onError={(e) => {
                    // Fallback to initials if icon fails to load
                    e.currentTarget.style.display = 'none';
                    const parent = e.currentTarget.parentElement!;
                    parent.classList.add(getColorClass(shortName));

                    // Create span element safely without innerHTML to prevent XSS
                    const span = document.createElement('span');
                    span.className = 'text-white font-semibold text-xs sm:text-sm';
                    span.textContent = shortName.substring(0, 2).toUpperCase();
                    parent.appendChild(span);
                }}
            />
        </div>
    );

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
                    <AuthProviderIcon />
                    <div className="flex flex-col">
                        <span className="text-xs sm:text-sm font-medium truncate">{name}</span>
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
