import { Menu } from "@base-ui/react/menu";
import { MoreHorizontal, RefreshCw, Trash2 } from "lucide-react";
import { getStatusColor, getStatusLabel } from "../lib/connection-utils";
import type {
  ConnectLabels,
  SourceConnectionListItem,
  SyncProgressUpdate,
} from "../lib/types";
import { AppIcon } from "./AppIcon";
import { SyncProgressIndicator } from "./SyncProgressIndicator";

interface ConnectionItemProps {
  connection: SourceConnectionListItem;
  onReconnect?: () => void;
  onDelete: () => void;
  labels: Required<ConnectLabels>;
  /** Real-time sync progress when connection is syncing */
  syncProgress?: SyncProgressUpdate | null;
  /** Whether the SSE connection is reconnecting */
  isSseReconnecting?: boolean;
}

export function ConnectionItem({
  connection,
  onReconnect,
  onDelete,
  labels,
  syncProgress,
  isSseReconnecting = false,
}: ConnectionItemProps) {
  const statusColor = getStatusColor(connection.status);
  const entitiesText = labels.entitiesCount.replace(
    "{count}",
    String(connection.entity_count),
  );

  return (
    <div
      className="flex items-center justify-between p-4 rounded-lg gap-3"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
      }}
    >
      <div className="flex items-center gap-3 grow truncate">
        <div className="shrink-0">
          <AppIcon shortName={connection.short_name} name={connection.name} />
        </div>
        <div className="grow truncate">
          <p
            className="font-medium text-sm"
            style={{ color: "var(--connect-text)" }}
          >
            {connection.name}
          </p>
          {syncProgress && connection.status === "syncing" ? (
            <SyncProgressIndicator
              progress={syncProgress}
              isReconnecting={isSseReconnecting}
            />
          ) : (
            <p
              className="text-xs"
              style={{ color: "var(--connect-text-muted)" }}
            >
              {entitiesText}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span
          className="text-xs px-2 py-1 rounded-full shrink-0 border"
          style={{
            backgroundColor: `color-mix(in srgb, ${statusColor} 5%, transparent)`,
            borderColor: `color-mix(in srgb, ${statusColor} 20%, transparent)`,
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
                {onReconnect && (
                  <Menu.Item
                    onClick={onReconnect}
                    className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded text-sm border-none bg-transparent w-full transition-colors duration-150 [color:var(--connect-text)] hover:bg-slate-500/10"
                  >
                    <RefreshCw size={14} />
                    <span>{labels.menuReconnect}</span>
                  </Menu.Item>
                )}
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
