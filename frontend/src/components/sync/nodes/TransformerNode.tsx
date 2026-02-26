import { memo } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import { cn } from "@/lib/utils";
import { getTransformerIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

export const TransformerNode = memo(({ data, selected, ...props }: NodeProps) => {
  const { resolvedTheme } = useTheme();
  // Use the model property if it exists (for embedding models), otherwise use transformerId
  const iconName = data.model || data.transformerId || 'default-transformer';
  console.log(`icon name:${getTransformerIconUrl(iconName)}`)

  return (
    <div className="w-10 h-10">
      <div
        className={cn(
          "w-full h-full flex items-center justify-center bg-background/80 backdrop-blur-sm",
          "border-[1px] transition-colors duration-200 cursor-pointer",
          "border-muted-foreground/50 hover:border-primary rounded-lg",
          selected ? "border-primary shadow-sm shadow-primary/20" : ""
        )}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="w-1 h-1 ml-[1px] border border-background bg-muted-foreground"
        />
        <div className="flex items-center justify-center">
          <img
            src={getTransformerIconUrl(iconName, resolvedTheme)}
            alt={data.name}
            className="w-6 h-6"
            onError={(e) => {
              // Fallback to initials if icon fails to load
              e.currentTarget.style.display = 'none';
              const parent = e.currentTarget.parentElement!;
              const initials = data.name?.substring(0, 2).toUpperCase() || 'TR';

              // Create span element safely without innerHTML to prevent XSS
              const span = document.createElement('span');
              span.className = 'text-foreground font-medium text-xs';
              span.textContent = initials;
              parent.appendChild(span);
            }}
          />
        </div>
        <Handle
          type="source"
          position={Position.Right}
          className="w-1 h-1 ml-[1px] border border-background bg-muted-foreground"
        />
      </div>
      <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-[8px] text-foreground text-center">
          {data.name}
        </span>
      </div>
    </div>
  );
});

TransformerNode.displayName = "TransformerNode";
