import * as React from 'react';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import {
  formatCollectionSearchReasoningEvent,
  getCollectionSearchReasoningSummarySections,
} from './collection-search-reasoning-model';
import type {
  CollectionSearchReasoningExpandedLine,
  CollectionSearchReasoningSection,
} from './collection-search-reasoning-model';
import type {
  CollectionSearchReasoningEvent,
  CollectionSearchTierState,
} from './use-collection-search-tiers';
import { cn } from '@/shared/tailwind/cn';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/ui/collapsible';
import { Separator } from '@/shared/ui/separator';

export function CollectionSearchReasoningTabContent({
  emptyState,
  events,
  finalEvent,
  isFinished = false,
  isLoading = false,
}: {
  emptyState?: React.ReactNode;
  events?: Array<CollectionSearchReasoningEvent>;
  finalEvent?: CollectionSearchTierState['rawFinalEvent'];
  isFinished?: boolean;
  isLoading?: boolean;
}) {
  const reasoningEvents = events ?? [];

  if (reasoningEvents.length === 0 && !isLoading) {
    return emptyState ?? null;
  }

  return (
    <div className="space-y-4">
      <div className="space-y-4">
        {reasoningEvents.map((event, index) => {
          const formattedEvent = formatCollectionSearchReasoningEvent(event);

          if (!formattedEvent) {
            return null;
          }

          return (
            <div
              key={`${event.type}-${index}`}
              className="flex flex-col gap-2 sm:flex-row sm:justify-between sm:gap-6"
            >
              <div className="min-w-0 space-y-1 md:max-w-110 lg:max-w-180">
                <p
                  className={cn(
                    'font-mono text-xs text-muted-foreground',
                    formattedEvent.isInvalid ? 'line-through opacity-50' : '',
                  )}
                >
                  {formattedEvent.label}
                  {formattedEvent.labelSuffix ? (
                    <span className="ml-2">{formattedEvent.labelSuffix}</span>
                  ) : null}
                </p>

                {formattedEvent.detailLines?.length ? (
                  <div className="space-y-0.5">
                    {formattedEvent.detailLines.map((detailLine, detailIndex) => (
                      <p
                        key={`${detailLine}-${detailIndex}`}
                        className="text-xs leading-4 text-foreground"
                      >
                        {detailLine}
                      </p>
                    ))}
                  </div>
                ) : null}

                {formattedEvent.sections?.length ? (
                  <div className="space-y-0.5">
                    {formattedEvent.sections.map((section, sectionIndex) => (
                      <CollectionSearchReasoningSectionLine
                        key={`${section.label}-${section.collapsed}-${sectionIndex}`}
                        section={section}
                      />
                    ))}
                  </div>
                ) : null}
              </div>

              {formattedEvent.metaLabel ? (
                <span className="shrink-0 self-start font-mono text-xs text-muted-foreground sm:self-center">
                  {formattedEvent.metaLabel}
                </span>
              ) : null}
            </div>
          );
        })}

        {isLoading ? <CollectionSearchReasoningPendingLine /> : null}
      </div>

      {isFinished ? (
        <CollectionSearchReasoningSummary finalEvent={finalEvent} />
      ) : null}
    </div>
  );
}

function CollectionSearchReasoningPendingLine() {
  return (
    <div className="animate-pulse font-mono text-xs text-muted-foreground">
      Thinking...
    </div>
  );
}

function CollectionSearchReasoningSummary({
  finalEvent,
}: {
  finalEvent?: CollectionSearchTierState['rawFinalEvent'];
}) {
  const sections = getCollectionSearchReasoningSummarySections(finalEvent);

  if (!sections.length) {
    return null;
  }

  return (
    <>
      <Separator />

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-xs text-muted-foreground">
        {sections.map((section, index) => (
          <React.Fragment key={section}>
            {index > 0 ? (
              <Separator
                aria-hidden="true"
                orientation="vertical"
                className="hidden h-5 sm:block"
              />
            ) : null}

            <span>{section}</span>
          </React.Fragment>
        ))}
      </div>
    </>
  );
}

function CollectionSearchReasoningSectionLine({
  section,
}: {
  section: CollectionSearchReasoningSection;
}) {
  const [open, setOpen] = React.useState(false);

  if (!section.collapsed) {
    return null;
  }

  const label = `${section.label}: `;

  if (section.expandedLines.length === 0) {
    return (
      <p className="ml-0.5 text-xs leading-4 text-muted-foreground">
        <span className="opacity-50">{label}</span>
        {section.collapsed}
      </p>
    );
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full max-w-full min-w-0 items-center gap-0.5 overflow-hidden text-left text-xs leading-4 text-muted-foreground hover:underline"
        >
          {open ? (
            <IconChevronDown className="size-3" />
          ) : (
            <IconChevronRight className="size-3" />
          )}

          <span className="shrink-0 opacity-50">{label}</span>
          <span className="min-w-0 flex-1 truncate">{section.collapsed}</span>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent className="ml-4 space-y-px">
        {section.expandedLines.map((expandedLine, index) => (
          <CollectionSearchReasoningExpandedLine
            key={`${getCollectionSearchReasoningExpandedLineKey(expandedLine)}-${index}`}
            expandedLine={expandedLine}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

function CollectionSearchReasoningExpandedLine({
  expandedLine,
}: {
  expandedLine: CollectionSearchReasoningExpandedLine;
}) {
  if (expandedLine.type === 'text') {
    return (
      <p className="truncate text-xs leading-4 text-muted-foreground">
        {expandedLine.content}
      </p>
    );
  }

  return (
    <p className="truncate text-xs leading-4 text-muted-foreground">
      <span>{expandedLine.label}</span>
      <span className="opacity-50">{expandedLine.metadata}</span>
    </p>
  );
}

function getCollectionSearchReasoningExpandedLineKey(
  expandedLine: CollectionSearchReasoningExpandedLine,
) {
  return expandedLine.type === 'text'
    ? expandedLine.content
    : `${expandedLine.label}${expandedLine.metadata}`;
}
