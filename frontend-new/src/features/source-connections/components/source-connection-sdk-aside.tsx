import * as React from 'react';
import { IconCheck, IconChevronDown, IconCopy } from '@tabler/icons-react';
import { sourceConnectionSdkSnippets } from '../lib/source-connection-sdk-snippets';
import { GetIdeReadySnippetButton } from './get-ide-ready-snippet-button';
import { OAuthFlowDiagram } from './oauth-flow-diagram';
import type {
  SourceConnectionSdkLanguage,
  SourceConnectionSdkSnippet,
} from '../lib/source-connection-sdk-snippets';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { Button } from '@/shared/ui/button';
import { CodeSnippet } from '@/shared/ui/code-snippet';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/ui/collapsible';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';

const SDK_LANGUAGE_OPTIONS = [
  { label: 'Python', value: 'python' },
  { label: 'Node.js', value: 'node' },
];

const CONFIG_SNIPPETS = sourceConnectionSdkSnippets.config satisfies Record<
  SourceConnectionSdkLanguage,
  SourceConnectionSdkSnippet
>;

const AUTH_SNIPPETS = sourceConnectionSdkSnippets.auth satisfies Record<
  SourceConnectionSdkLanguage,
  SourceConnectionSdkSnippet
>;

const SYNC_SNIPPETS = sourceConnectionSdkSnippets.sync satisfies Record<
  SourceConnectionSdkLanguage,
  SourceConnectionSdkSnippet
>;

export function ConnectSourceConfigSdkAside({ sourceName }: { sourceName: string }) {
  return <SourceConnectionSdkAside snippets={CONFIG_SNIPPETS} sourceName={sourceName} />;
}

export function ConnectSourceAuthSdkAside({ sourceName }: { sourceName: string }) {
  return <SourceConnectionSdkAside snippets={AUTH_SNIPPETS} sourceName={sourceName} />;
}

export function ConnectSourceSyncSdkAside({ sourceName }: { sourceName: string }) {
  return <SourceConnectionSdkAside snippets={SYNC_SNIPPETS} sourceName={sourceName} />;
}

function SourceConnectionSdkAside({
  snippets,
  sourceName,
}: {
  snippets: Record<SourceConnectionSdkLanguage, SourceConnectionSdkSnippet>;
  sourceName: string;
}) {
  const { copied, copy } = useCopyToClipboard();
  const [language, setLanguage] =
    React.useState<SourceConnectionSdkLanguage>('python');
  const activeSnippet = snippets[language];

  return (
    <div className="flex min-h-0 flex-col text-card-foreground lg:h-full">
      <Collapsible className="group shrink-0 border-b border-border">
        <CollapsibleTrigger className="flex h-11 w-full items-center gap-3 px-4 text-left">
          <p className="font-mono text-xs font-medium text-muted-foreground uppercase">
            See how Airweave handles OAuth
          </p>
          <IconChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
        </CollapsibleTrigger>

        <CollapsibleContent className="border-t border-border px-4 py-4">
          <OAuthFlowDiagram sourceName={sourceName} />
        </CollapsibleContent>
      </Collapsible>

      <div className="px-4 py-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
        <SdkSnippetSection
          actions={
            <>
              <Select
                value={language}
                onValueChange={(nextLanguage: SourceConnectionSdkLanguage) =>
                  setLanguage(nextLanguage)
                }
              >
                <SelectTrigger
                  aria-label="Select code language"
                  size="sm"
                  className="!h-5.5 dark:bg-transparent"
                >
                  <SelectValue />
                </SelectTrigger>

                <SelectContent>
                  {SDK_LANGUAGE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => void copy(activeSnippet.requestCode)}
              >
                {copied ? (
                  <IconCheck className="size-3.5" />
                ) : (
                  <IconCopy className="size-3.5" />
                )}
                <span className="sr-only">Copy request snippet</span>
              </Button>
            </>
          }
          label="Request"
        >
          <CodeSnippet
            className="text-card-foreground"
            code={activeSnippet.requestCode}
            language={language === 'python' ? 'python' : 'typescript'}
          />
        </SdkSnippetSection>

        <SdkSnippetSection label="Response">
          <CodeSnippet
            className="text-card-foreground"
            code={activeSnippet.responseCode}
            language={language === 'python' ? 'python' : 'typescript'}
          />
        </SdkSnippetSection>
      </div>

      <div className="shrink-0 p-6">
        <GetIdeReadySnippetButton />
      </div>
    </div>
  );
}

function SdkSnippetSection({
  actions,
  children,
  label,
}: {
  actions?: React.ReactNode;
  children: React.ReactNode;
  label: string;
}) {
  return (
    <section className="space-y-3 border-b border-border py-4 first:pt-0 last:border-b-0 last:pb-0">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-xs font-medium text-muted-foreground uppercase">
          {label}
        </p>

        {actions ? (
          <div className="flex items-center gap-2">{actions}</div>
        ) : null}
      </div>

      {children}
    </section>
  );
}
