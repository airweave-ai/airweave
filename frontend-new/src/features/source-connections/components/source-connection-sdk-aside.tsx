import * as React from 'react';
import { IconChevronDown } from '@tabler/icons-react';
import { sourceConnectionSdkSnippets } from '../lib/source-connection-sdk-snippets';
import { OAuthFlowDiagram } from './oauth-flow-diagram';
import type {
  SourceConnectionSdkLanguage,
  SourceConnectionSdkSnippet,
} from '../lib/source-connection-sdk-snippets';
import {
  CodeSnippetAside,
  CodeSnippetAsideContent,
  CodeSnippetAsideLanguageSelect,
  CodeSnippetAsideSection,
  CopyCodeSnippetButton,
  codeSnippetLanguageOptions,
} from '@/shared/components/code-snippet-aside';
import { GetIdeReadySnippetButton } from '@/shared/components/get-ide-ready-snippet-button';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { CodeSnippet } from '@/shared/ui/code-snippet';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/ui/collapsible';

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

export function ConnectSourceConfigSdkAside({
  sourceName,
}: {
  sourceName: string;
}) {
  return (
    <SourceConnectionSdkAside
      snippets={CONFIG_SNIPPETS}
      sourceName={sourceName}
    />
  );
}

export function ConnectSourceAuthSdkAside({
  sourceName,
}: {
  sourceName: string;
}) {
  return (
    <SourceConnectionSdkAside
      snippets={AUTH_SNIPPETS}
      sourceName={sourceName}
    />
  );
}

export function ConnectSourceSyncSdkAside({
  sourceName,
}: {
  sourceName: string;
}) {
  return (
    <SourceConnectionSdkAside
      snippets={SYNC_SNIPPETS}
      sourceName={sourceName}
    />
  );
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
    <CodeSnippetAside>
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

      <CodeSnippetAsideContent>
        <CodeSnippetAsideSection
          actions={
            <>
              <CodeSnippetAsideLanguageSelect
                options={codeSnippetLanguageOptions}
                value={language}
                onValueChange={setLanguage}
              />
              <CopyCodeSnippetButton
                copied={copied}
                onClick={() => void copy(activeSnippet.requestCode)}
              />
            </>
          }
          label="Request"
        >
          <CodeSnippet
            className="text-card-foreground"
            code={activeSnippet.requestCode}
            language={language === 'python' ? 'python' : 'typescript'}
          />
        </CodeSnippetAsideSection>

        <CodeSnippetAsideSection label="Response">
          <CodeSnippet
            className="text-card-foreground"
            code={activeSnippet.responseCode}
            language={language === 'python' ? 'python' : 'typescript'}
          />
        </CodeSnippetAsideSection>
      </CodeSnippetAsideContent>

      <div className="shrink-0 px-4 pt-3 pb-6">
        <GetIdeReadySnippetButton />
      </div>
    </CodeSnippetAside>
  );
}
