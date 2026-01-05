/**
 * SourceSelectView - Grid of available sources to select from
 */

import { useQuery } from "@tanstack/react-query";
import { Loader2, Search, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useIsDark } from "@/hooks/use-is-dark";
import { fetchSources, type Source } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { cn } from "@/lib/utils";

import { getAppIconUrl } from "../../utils/helpers";

/**
 * Source descriptions for tooltips
 */
const SOURCE_DESCRIPTIONS: Record<string, string> = {
  notion: "Connect to Notion to sync pages, databases, and workspace content.",
  postgresql:
    "Connect to PostgreSQL to sync tables, views, schemas, and records.",
  jira: "Connect to Jira to sync issues, projects, and team workflows.",
  hubspot:
    "Connect to HubSpot to sync contacts, companies, deals, and CRM data.",
  google_calendar:
    "Connect to Google Calendar to sync events and scheduling data.",
  google_drive:
    "Connect to Google Drive to sync files, folders, and documents.",
  gmail: "Connect to Gmail to sync email threads and attachments.",
  confluence: "Connect to Confluence to sync pages, spaces, and documentation.",
  todoist: "Connect to Todoist to sync projects, tasks, and productivity data.",
  github: "Connect to GitHub to sync repositories and code files.",
  stripe:
    "Connect to Stripe to sync customers, transactions, and billing data.",
  dropbox: "Connect to Dropbox to sync files and cloud storage data.",
  asana: "Connect to Asana to sync workspaces, projects, and tasks.",
  outlook_calendar: "Connect to Outlook Calendar to sync events and meetings.",
  outlook_mail: "Connect to Outlook Mail to sync emails and folders.",
  onedrive: "Connect to OneDrive to sync files and cloud storage.",
  monday: "Connect to Monday to sync boards and project management data.",
  bitbucket: "Connect to Bitbucket to sync repositories and pull requests.",
  linear: "Connect to Linear to sync issues and engineering workflows.",
  slack: "Connect to Slack to sync messages and channel data.",
};

interface SourceSelectViewProps {
  onSelectSource: (shortName: string, displayName: string) => void;
  onCancel: () => void;
}

export function SourceSelectView({
  onSelectSource,
  onCancel,
}: SourceSelectViewProps) {
  const isDark = useIsDark();
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch available sources
  const { data: sources = [], isLoading } = useQuery({
    queryKey: ["sources", organization?.id],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSources(token, organization!.id);
    },
    enabled: !!organization,
  });

  // Filter sources based on search
  const filteredSources = useMemo(() => {
    if (!searchQuery) return sources;

    const query = searchQuery.toLowerCase();
    return sources.filter(
      (source) =>
        source.name.toLowerCase().includes(query) ||
        source.short_name.toLowerCase().includes(query) ||
        source.description?.toLowerCase().includes(query)
    );
  }, [sources, searchQuery]);

  // Sort sources alphabetically
  const sortedSources = useMemo(() => {
    return [...filteredSources].sort((a, b) => a.name.localeCompare(b.name));
  }, [filteredSources]);

  const handleSelectSource = useCallback(
    (source: Source) => {
      onSelectSource(source.short_name, source.name);
    },
    [onSelectSource]
  );

  const getSourceDescription = (source: Source) => {
    return (
      SOURCE_DESCRIPTIONS[source.short_name] ||
      source.description ||
      `Connect to ${source.name} to sync your data.`
    );
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header with search */}
      <div className="border-b px-6 py-4">
        <div className="mb-4">
          <h2
            className={cn(
              "text-xl font-semibold",
              isDark ? "text-white" : "text-gray-900"
            )}
          >
            Select a source
          </h2>
          <p
            className={cn(
              "text-sm",
              isDark ? "text-gray-400" : "text-gray-500"
            )}
          >
            Choose a data source to connect to your collection
          </p>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search
            className={cn(
              "absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2",
              isDark ? "text-gray-500" : "text-gray-400"
            )}
          />
          <Input
            type="text"
            placeholder="Search sources..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={cn(
              "pr-8 pl-9",
              isDark
                ? "border-gray-700 bg-gray-800 placeholder:text-gray-500"
                : "border-gray-200 bg-white placeholder:text-gray-400"
            )}
            autoFocus
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className={cn(
                "absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 transition-colors",
                isDark ? "hover:bg-gray-700" : "hover:bg-gray-100"
              )}
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Results count */}
        <div
          className={cn(
            "mt-2 text-xs",
            isDark ? "text-gray-500" : "text-gray-400"
          )}
        >
          {sortedSources.length}{" "}
          {sortedSources.length === 1 ? "source" : "sources"} available
        </div>
      </div>

      {/* Source grid */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
          </div>
        ) : sortedSources.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-muted-foreground">
              {searchQuery ? "No sources found" : "No sources available"}
            </p>
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="mt-2 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5">
            {sortedSources.map((source) => (
              <TooltipProvider key={source.short_name} delayDuration={300}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => handleSelectSource(source)}
                      className={cn(
                        "group flex flex-col items-center gap-2 rounded-lg border p-4 transition-all",
                        isDark
                          ? "border-gray-800 bg-gray-900/50 hover:border-gray-700 hover:bg-gray-900"
                          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
                      )}
                    >
                      {/* Source icon */}
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-md">
                        <img
                          src={getAppIconUrl(
                            source.short_name,
                            isDark ? "dark" : "light"
                          )}
                          alt={source.name}
                          className="h-full w-full object-contain"
                          onError={(e) => {
                            // Hide image and show fallback
                            (e.target as HTMLImageElement).style.display =
                              "none";
                            const parent = (e.target as HTMLImageElement)
                              .parentElement;
                            if (parent) {
                              parent.innerHTML = `<span class="flex h-full w-full items-center justify-center rounded-md ${
                                isDark
                                  ? "bg-gray-700 text-gray-300"
                                  : "bg-gray-100 text-gray-600"
                              } text-lg font-semibold">${source.name.charAt(0).toUpperCase()}</span>`;
                            }
                          }}
                        />
                      </div>

                      {/* Source name */}
                      <span
                        className={cn(
                          "line-clamp-1 text-center text-xs font-medium",
                          isDark ? "text-white" : "text-gray-900"
                        )}
                      >
                        {source.name}
                      </span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    className={cn(
                      "max-w-xs border p-4 shadow-lg",
                      isDark
                        ? "border-gray-700 bg-gray-900 text-gray-100"
                        : "border-gray-200 bg-white text-gray-900"
                    )}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <img
                          src={getAppIconUrl(
                            source.short_name,
                            isDark ? "dark" : "light"
                          )}
                          alt={source.name}
                          className="h-5 w-5 rounded-sm"
                        />
                        <span className="text-sm font-semibold">
                          {source.name}
                        </span>
                      </div>
                      <p className="text-muted-foreground text-sm leading-relaxed">
                        {getSourceDescription(source)}
                      </p>
                      {source.labels && source.labels.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {source.labels.map((label, idx) => (
                            <span
                              key={idx}
                              className={cn(
                                "rounded-full px-2 py-0.5 text-xs",
                                isDark
                                  ? "bg-gray-800 text-gray-300"
                                  : "bg-gray-100 text-gray-600"
                              )}
                            >
                              {label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        )}
      </div>

      {/* Footer with cancel button */}
      <div
        className={cn(
          "border-t px-6 py-4",
          isDark ? "border-gray-800" : "border-gray-200"
        )}
      >
        <button
          onClick={onCancel}
          className={cn(
            "text-sm font-medium transition-colors",
            isDark
              ? "text-gray-400 hover:text-gray-200"
              : "text-gray-600 hover:text-gray-900"
          )}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
