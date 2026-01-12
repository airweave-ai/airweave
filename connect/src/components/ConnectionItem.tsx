import { Menu } from "@base-ui/react/menu";
import { MoreHorizontal, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { getStatusColor, getStatusLabel } from "../lib/connection-utils";
import { getAppIconUrl } from "../lib/icons";
import { useTheme } from "../lib/theme";
import type { ConnectLabels, SourceConnectionListItem } from "../lib/types";

interface ConnectionItemProps {
  connection: SourceConnectionListItem;
  onDelete: () => void;
  isDeleting: boolean;
  labels: Required<ConnectLabels>;
}

export function ConnectionItem({
  connection,
  onDelete,
  isDeleting,
  labels,
}: ConnectionItemProps) {
  const { resolvedMode } = useTheme();
  const [imgError, setImgError] = useState(false);
  const statusColor = getStatusColor(connection.status);
  const entitiesText = labels.entitiesCount.replace(
    "{count}",
    String(connection.entity_count),
  );

  return (
    <div
      className="flex items-center justify-between p-4 rounded-lg"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
        opacity: isDeleting ? 0.5 : 1,
      }}
    >
      <div className="flex items-center gap-3">
        {imgError ? (
          <div
            className="size-8 rounded-lg flex items-center justify-center text-sm font-medium uppercase"
            style={{
              backgroundColor:
                "color-mix(in srgb, var(--connect-primary) 20%, transparent)",
              color: "var(--connect-primary)",
            }}
          >
            {connection.short_name.slice(0, 2)}
          </div>
        ) : (
          <img
            src={getAppIconUrl(connection.short_name, resolvedMode)}
            alt={connection.name}
            className="size-8 object-contain"
            onError={() => setImgError(true)}
          />
        )}
        <div>
          <p
            className="font-medium text-sm"
            style={{ color: "var(--connect-text)" }}
          >
            {connection.name}
          </p>
          <p className="text-xs" style={{ color: "var(--connect-text-muted)" }}>
            {entitiesText}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span
          className="text-xs px-2 py-1 rounded-full"
          style={{
            backgroundColor: `color-mix(in srgb, ${statusColor} 20%, transparent)`,
            color: statusColor,
          }}
        >
          {getStatusLabel(connection.status, labels)}
        </span>
        <Menu.Root>
          <Menu.Trigger className="p-1 rounded cursor-pointer border-none bg-transparent flex items-center justify-center transition-colors duration-150 hover:bg-black/10 dark:hover:bg-white/10 [color:var(--connect-text-muted)] hover:[color:var(--connect-text)]">
            <MoreHorizontal size={16} />
          </Menu.Trigger>
          <Menu.Portal>
            <Menu.Positioner side="bottom" align="end" sideOffset={4}>
              <Menu.Popup className="dropdown-popup min-w-[140px] rounded-lg p-1 shadow-lg [background-color:var(--connect-surface)] [border:1px_solid_var(--connect-border)]">
                <Menu.Item
                  onClick={() => {
                    /* no-op for now */
                  }}
                  className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded text-sm border-none bg-transparent w-full transition-colors duration-150 [color:var(--connect-text)] hover:bg-slate-500/10"
                >
                  <RefreshCw size={14} />
                  <span>{labels.menuReconnect}</span>
                </Menu.Item>
                <Menu.Item
                  onClick={onDelete}
                  className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded text-sm border-none bg-transparent w-full transition-colors duration-150 [color:var(--connect-error)] hover:bg-red-500/10"
                >
                  <Trash2 size={14} />
                  <span>{labels.menuDelete}</span>
                </Menu.Item>
              </Menu.Popup>
            </Menu.Positioner>
          </Menu.Portal>
        </Menu.Root>
      </div>
    </div>
  );
}
