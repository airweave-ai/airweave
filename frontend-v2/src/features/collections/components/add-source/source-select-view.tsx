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

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ["sources", organization?.id],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSources(token, organization!.id);
    },
    enabled: !!organization,
  });

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
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Select a source
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Choose a data source to connect to your collection
          </p>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <Input
            type="text"
            placeholder="Search sources..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="border-gray-200 bg-white pr-8 pl-9 placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
            autoFocus
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Results count */}
        <div className="mt-2 text-xs text-gray-400 dark:text-gray-500">
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
                      className="group flex flex-col items-center gap-2 rounded-lg border border-gray-200 bg-white p-4 transition-all hover:border-gray-300 hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900/50 dark:hover:border-gray-700 dark:hover:bg-gray-900"
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
                      <span className="line-clamp-1 text-center text-xs font-medium text-gray-900 dark:text-white">
                        {source.name}
                      </span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    className="max-w-xs border border-gray-200 bg-white p-4 text-gray-900 shadow-lg dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
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
                              className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300"
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
      <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-800">
        <button
          onClick={onCancel}
          className="text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
