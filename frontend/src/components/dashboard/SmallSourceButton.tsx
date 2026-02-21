import { Button } from "@/components/ui/button";
import { Plus, Check } from "lucide-react";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";

interface SmallSourceButtonProps {
    id: string;
    name: string;
    shortName: string;
    connected?: boolean;
    onClick?: () => void;
}

export const SmallSourceButton = ({ id, name, shortName, connected = false, onClick }: SmallSourceButtonProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    // Get color class based on shortName
    const getColorClass = (shortName: string) => {
        const colors = [
            "bg-blue-500",
            "bg-blue-500",
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

    // Source icon component
    const SourceIcon = () => (
        <div className="flex items-center justify-center w-10 h-10 overflow-hidden rounded-md flex-shrink-0">
            <img
                src={getAppIconUrl(shortName, resolvedTheme)}
                alt={`${shortName} icon`}
                className="w-9 h-9 object-contain"
                onError={(e) => {
                    // Fallback to initials if icon fails to load
                    e.currentTarget.style.display = 'none';
                    const parent = e.currentTarget.parentElement!;
                    parent.classList.add(getColorClass(shortName));

                    // Create span element safely without innerHTML to prevent XSS
                    const span = document.createElement('span');
                    span.className = 'text-white font-semibold text-sm';
                    span.textContent = shortName.substring(0, 2).toUpperCase();
                    parent.appendChild(span);
                }}
            />
        </div>
    );

    return (
        <div
            className={cn(
                "border rounded-lg overflow-hidden transition-all min-w-[100px] h-[60px]",
                connected ? (
                    // Connected sources - no hover effects, no cursor pointer
                    isDark
                        ? "border-blue-400 bg-blue-500/20"
                        : "border-blue-500 bg-blue-50"
                ) : (
                    // Unconnected sources - with hover effects and cursor pointer
                    isDark
                        ? "border-gray-800 hover:border-gray-700 bg-gray-900/50 hover:bg-gray-900 cursor-pointer group"
                        : "border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50 cursor-pointer group"
                )
            )}
            onClick={() => {
                console.log('🔲 [SmallSourceButton] Button clicked:', { id, name, shortName, connected });
                onClick?.();
            }}
            title={connected ? `${name} (Connected)` : name}
        >
            <div className="p-2 flex items-center justify-between h-full">
                {connected ? (
                    // For connected sources, render a static div instead of interactive Button
                    <div
                        className={cn(
                            "h-6 w-6 rounded-full flex-shrink-0 flex items-center justify-center",
                            isDark
                                ? "bg-blue-600/60 text-blue-200"
                                : "bg-blue-500 text-white"
                        )}
                    >
                        <Check className="h-3 w-3" />
                    </div>
                ) : (
                    // For unconnected sources, render interactive Button
                    <Button
                        size="icon"
                        variant="ghost"
                        className={cn(
                            "h-6 w-6 rounded-full flex-shrink-0",
                            isDark
                                ? "bg-gray-800/80 text-blue-400 hover:bg-blue-600/20 hover:text-blue-300 group-hover:bg-blue-600/30"
                                : "bg-gray-100/80 text-blue-500 hover:bg-blue-100 hover:text-blue-600 group-hover:bg-blue-100/80"
                        )}
                    >
                        <Plus className="h-3 w-3 group-hover:h-3.5 group-hover:w-3.5 transition-all" />
                    </Button>
                )}
                <SourceIcon />
            </div>
        </div>
    );
};

export default SmallSourceButton;
