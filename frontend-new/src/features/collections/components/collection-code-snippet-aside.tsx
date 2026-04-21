import * as React from 'react';
import { IconLayoutSidebarRight } from '@tabler/icons-react';
import { createCollectionCodeSnippets } from '../lib/collection-code-snippets';
import { getCollectionSearchConfig } from '../lib/collection-search-request';
import type { CollectionSearchWorkspaceForm } from './collection-search/use-collection-search-workspace';
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
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { CodeSnippet } from '@/shared/ui/code-snippet';

type CollectionCodeSnippetAsideLanguage =
  (typeof codeSnippetLanguageOptions)[number]['value'];

export function CollectionCodeSnippetAside({
  collapsed,
  collectionId,
  form,
  onCollapseToggle,
}: {
  collapsed: boolean;
  collectionId: string;
  form: CollectionSearchWorkspaceForm;
  onCollapseToggle: () => void;
}) {
  return (
    <form.Subscribe
      selector={(state) => ({
        config: getCollectionSearchConfig(state.values),
        query: state.values.query,
      })}
    >
      {({ config, query }) => (
        <CollectionCodeSnippetAsideContent
          collapsed={collapsed}
          collectionId={collectionId}
          config={config}
          onCollapseToggle={onCollapseToggle}
          query={query}
        />
      )}
    </form.Subscribe>
  );
}

function CollectionCodeSnippetAsideContent({
  collapsed,
  collectionId,
  config,
  onCollapseToggle,
  query,
}: {
  collapsed: boolean;
  collectionId: string;
  config: ReturnType<typeof getCollectionSearchConfig>;
  onCollapseToggle: () => void;
  query: string;
}) {
  const { copied, copy } = useCopyToClipboard();
  const [language, setLanguage] =
    React.useState<CollectionCodeSnippetAsideLanguage>('python');
  const snippets = React.useMemo(
    () => createCollectionCodeSnippets({ collectionId, config, query }),
    [collectionId, config, query],
  );
  const activeSnippet = snippets[language];

  return (
    <div className="min-w-0 lg:h-full lg:min-h-0 lg:self-stretch">
      <div
        className={cn(
          'border-t border-border bg-background text-card-foreground lg:h-full lg:min-h-0 lg:border-t-0 lg:border-l',
          collapsed && 'lg:hidden',
        )}
      >
        <CodeSnippetAside>
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

                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="hidden lg:inline-flex"
                    onClick={onCollapseToggle}
                  >
                    <IconLayoutSidebarRight className="size-3.5" />
                    <span className="sr-only">Collapse code snippets</span>
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
            </CodeSnippetAsideSection>

            <CodeSnippetAsideSection label="Response">
              <CodeSnippet
                className="text-card-foreground"
                code={activeSnippet.responseCode}
                language={language === 'python' ? 'python' : 'typescript'}
              />
            </CodeSnippetAsideSection>
          </CodeSnippetAsideContent>

          <div className="shrink-0 p-4">
            <GetIdeReadySnippetButton />
          </div>
        </CodeSnippetAside>
      </div>

      <div
        className={cn(
          'hidden border-l border-border bg-background text-card-foreground lg:flex lg:h-full lg:min-h-0 lg:items-start lg:justify-center lg:px-2 lg:py-4',
          collapsed ? '' : 'lg:hidden',
        )}
      >
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onCollapseToggle}
        >
          <IconLayoutSidebarRight className="size-3.5" />
          <span className="sr-only">Expand code snippets</span>
        </Button>
      </div>
    </div>
  );
}
