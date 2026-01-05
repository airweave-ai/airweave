/**
 * EntityResultCard - A human-readable card view for entity search results
 */

import { Clock, ExternalLink, Link as LinkIcon } from "lucide-react";
import React, { useMemo } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { getAppIconUrl } from "@/features/collections";

import { ResultCollapsibleSection } from "./result-collapsible-section";
import { ResultScoreBadge } from "./result-score-badge";

interface EntityResultCardProps {
  result: Record<string, unknown>;
  index: number;
}

const arePropsEqual = (
  prevProps: EntityResultCardProps,
  nextProps: EntityResultCardProps
) => {
  return (
    prevProps.index === nextProps.index &&
    (prevProps.result as { id?: string }).id ===
      (nextProps.result as { id?: string }).id &&
    (prevProps.result as { score?: number }).score ===
      (nextProps.result as { score?: number }).score
  );
};

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    const timeStr = date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

    if (diffDays === 0) return `Today at ${timeStr}`;
    if (diffDays === 1) return `Yesterday at ${timeStr}`;
    if (diffDays < 7) return `${diffDays} days ago`;

    return (
      date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }) +
      " at " +
      timeStr
    );
  } catch {
    return dateString;
  }
}

function extractEntityType(rawEntityType: string, sourceName: string): string {
  let entityTypeCore = rawEntityType.replace(/Entity$/, "");
  if (entityTypeCore && sourceName) {
    const normalizedSource = sourceName.replace(/[\s_-]/g, "");
    if (normalizedSource) {
      const prefixRegex = new RegExp(
        `^${normalizedSource.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
        "i"
      );
      const condensedEntity = entityTypeCore.replace(/[\s_-]/g, "");
      if (prefixRegex.test(condensedEntity)) {
        entityTypeCore = entityTypeCore.slice(normalizedSource.length);
      }
    }
  }
  return entityTypeCore
    ? entityTypeCore.replace(/([A-Z])/g, " $1").trim() || "Document"
    : "Document";
}

const EntityResultCardComponent: React.FC<EntityResultCardProps> = ({
  result,
  index,
}) => {
  const payload = (result.payload as Record<string, unknown>) || result;
  const score = result.score as number | undefined;

  const systemMetadata = payload.airweave_system_metadata as
    | Record<string, unknown>
    | undefined;
  const entityId =
    (payload.entity_id as string) ||
    (payload.id as string) ||
    (payload._id as string);
  const sourceName =
    (systemMetadata?.source_name as string) ||
    (payload.source_name as string) ||
    "Unknown Source";
  const sourceIconUrl = getAppIconUrl(sourceName);
  const textualRepresentation =
    (payload.textual_representation as string) || "";
  const breadcrumbs = (payload.breadcrumbs as string[]) || [];
  const webUrl = payload.web_url as string | undefined;
  const url = payload.url as string | undefined;
  const openUrl = webUrl || url;
  const hasDownloadUrl = Boolean(url && webUrl && url !== webUrl);

  const title = (payload.name as string) || "Untitled";
  const rawEntityType = (systemMetadata?.entity_type as string) || "";
  const entityType = extractEntityType(rawEntityType, sourceName);
  const context =
    breadcrumbs.length > 0
      ? breadcrumbs
          .map((b) =>
            typeof b === "string" ? b : (b as { name?: string }).name || ""
          )
          .filter(Boolean)
          .join(" > ")
      : "";

  const relevantTimestamp =
    (payload.updated_at as string) || (payload.created_at as string);

  const formattedSourceName = sourceName
    .split("_")
    .map(
      (word: string) =>
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    )
    .join(" ");

  const metadata = useMemo(() => {
    const filtered: Record<string, unknown> = {};
    const excludeKeys = [
      "entity_id",
      "id",
      "_id",
      "textual_representation",
      "name",
      "breadcrumbs",
      "url",
      "web_url",
      "airweave_system_metadata",
      "source_name",
      "created_at",
      "updated_at",
      "vector",
      "vectors",
    ];

    Object.entries(payload).forEach(([key, value]) => {
      if (
        !excludeKeys.includes(key) &&
        value !== null &&
        value !== undefined &&
        value !== ""
      ) {
        const formattedKey = key
          .split("_")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" ");
        filtered[formattedKey] = value;
      }
    });

    return filtered;
  }, [payload]);

  const hasMetadata = Object.keys(metadata).length > 0;

  return (
    <div
      data-entity-id={entityId}
      className="group bg-card relative overflow-hidden rounded-xl border transition-all duration-300"
    >
      {/* Header Section */}
      <div className="border-b px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          {/* Title with Icon */}
          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-2.5">
              {/* Source Icon */}
              <div
                className="bg-muted flex size-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg"
                title={formattedSourceName}
              >
                <img
                  src={sourceIconUrl}
                  alt={formattedSourceName}
                  className="size-full object-contain p-1.5"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
              </div>
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <h3 className="text-foreground text-[14px] leading-snug font-semibold tracking-tight break-words">
                    {title}
                  </h3>
                  {openUrl && (
                    <div className="flex flex-wrap items-center gap-2">
                      <a
                        href={openUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 transition-all duration-200 hover:gap-2 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                      >
                        <ExternalLink className="size-3" />
                        Open in {formattedSourceName}
                      </a>
                      {hasDownloadUrl && (
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 transition-all duration-200 hover:gap-1.5 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          <LinkIcon className="size-3" />
                          Download original
                        </a>
                      )}
                    </div>
                  )}
                </div>

                {/* Context and Type */}
                <div className="mb-0 flex flex-wrap items-center gap-1">
                  <span className="text-foreground bg-muted inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium">
                    {entityType}
                  </span>
                  {context && context.length > 0 && (
                    <span className="text-muted-foreground bg-muted/50 inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium">
                      {context}
                    </span>
                  )}

                  {/* Last Updated Timestamp */}
                  {relevantTimestamp && (
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="text-muted-foreground bg-muted/30 inline-flex cursor-help items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium">
                            <Clock className="size-3" strokeWidth={1.5} />
                            {formatDate(relevantTimestamp)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          <div className="space-y-1">
                            <div className="text-[11px] font-bold tracking-wide">
                              {payload.updated_at ? "Last Updated" : "Created"}
                            </div>
                            <div className="font-mono text-[12px]">
                              {new Date(relevantTimestamp).toLocaleString(
                                "en-US",
                                {
                                  year: "numeric",
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                  hour12: true,
                                }
                              )}
                            </div>
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Score Badge */}
          <ResultScoreBadge index={index} score={score} />
        </div>
      </div>

      {/* Preview Section - Collapsible */}
      {textualRepresentation && (
        <ResultCollapsibleSection
          title="Preview"
          showCopyButton
          copyText={textualRepresentation}
        >
          <div className="text-foreground max-h-[200px] overflow-hidden pr-8">
            <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
              {textualRepresentation.length > 500
                ? textualRepresentation.substring(0, 500) + "..."
                : textualRepresentation}
            </p>
          </div>
        </ResultCollapsibleSection>
      )}

      {/* Properties Section - Collapsible */}
      {hasMetadata && (
        <ResultCollapsibleSection
          title="Properties"
          count={Object.keys(metadata).length}
        >
          <div className="bg-muted/30 -mx-4 px-4 pb-2.5">
            <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
              {Object.entries(metadata)
                .slice(0, 8)
                .map(([key, value]) => (
                  <div key={key} className="flex flex-col gap-1">
                    <div className="flex items-start gap-2.5">
                      <span className="text-muted-foreground min-w-[80px] pt-0.5 text-[10px] font-semibold tracking-wider uppercase">
                        {key}
                      </span>
                      <span className="text-muted-foreground flex-1 text-[12px] leading-snug break-words">
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value).length > 100
                            ? String(value).substring(0, 100) + "..."
                            : String(value)}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </ResultCollapsibleSection>
      )}
    </div>
  );
};

export const EntityResultCard = React.memo(
  EntityResultCardComponent,
  arePropsEqual
);
