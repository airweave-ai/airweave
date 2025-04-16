import { memo } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import { SplitSquareHorizontal, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";

const getTransformerIcon = (transformerId: string) => {
  switch (transformerId) {
    case 'text-splitter':
      return <SplitSquareHorizontal className="w-12 h-12" />;
    default:
      return <Wand2 className="w-12 h-12" />;
  }
};

export const TransformerNode = memo(({ data, selected, ...props }: NodeProps) => {
  return (
    <div className="w-20 h-20">
      <div
        className={cn(
          "w-full h-full flex items-center justify-center bg-background/80 backdrop-blur-sm",
          "border-2 transition-colors duration-200 cursor-pointer",
          "border-muted-foreground/50 hover:border-primary rounded-lg",
          selected ? "border-primary shadow-sm shadow-primary/20" : ""
        )}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="w-3 h-3 -ml-[3px] border border-background bg-muted-foreground"
        />
        <div className="w-16 h-16 flex items-center justify-center">
          {getTransformerIcon(data.transformer_id)}
        </div>
        <Handle
          type="source"
          position={Position.Right}
          className="w-3 h-3 -mr-[3px] border border-background bg-muted-foreground"
        />
      </div>
      <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-sm font-semibold text-foreground text-center">{data.name}</span>
      </div>
    </div>
  );
});

TransformerNode.displayName = "TransformerNode";
