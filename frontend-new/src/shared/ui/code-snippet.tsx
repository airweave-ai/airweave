import * as React from 'react';
import { createHighlighterCore } from 'shiki/core';
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript';
import { cn } from '@/shared/tailwind/cn';

export type CodeSnippetLanguage =
  | 'bash'
  | 'javascript'
  | 'json'
  | 'python'
  | 'typescript';

const SHIKI_THEME = 'dark-plus-transparent';
const highlighterPromise = createHighlighterCore({
  engine: createJavaScriptRegexEngine(),
  langs: [
    import('@shikijs/langs/bash'),
    import('@shikijs/langs/javascript'),
    import('@shikijs/langs/json'),
    import('@shikijs/langs/python'),
    import('@shikijs/langs/typescript'),
  ],
  themes: [
    import('@shikijs/themes/dark-plus').then(({ default: theme }) => ({
      ...theme,
      bg: '#00000000',
      colors: {
        ...theme.colors,
        'editor.background': '#00000000',
      },
      name: SHIKI_THEME,
    })),
  ],
});

async function highlightCode(code: string, language: CodeSnippetLanguage) {
  const highlighter = await highlighterPromise;

  return highlighter.codeToHtml(code, {
    lang: language,
    theme: SHIKI_THEME,
  });
}

export function CodeSnippet({
  className,
  code,
  language,
}: {
  className?: string;
  code: string;
  language: CodeSnippetLanguage;
}) {
  const [highlightedCode, setHighlightedCode] = React.useState<string | null>(
    null,
  );

  React.useEffect(() => {
    let isDisposed = false;

    setHighlightedCode(null);

    void highlightCode(code, language)
      .then((html) => {
        if (!isDisposed) {
          setHighlightedCode(html);
        }
      })
      .catch(() => {
        if (!isDisposed) {
          setHighlightedCode(null);
        }
      });

    return () => {
      isDisposed = true;
    };
  }, [code, language]);

  const contentClassName = cn(
    'min-w-0 font-mono text-xs leading-5 font-medium text-current',
    '[&_.line]:block [&_code]:grid [&_pre.shiki]:!m-0 [&_pre.shiki]:overflow-visible [&_pre.shiki]:!p-0 [&_pre.shiki]:break-words [&_pre.shiki]:!whitespace-pre-wrap',
    className,
  );

  if (highlightedCode == null) {
    return (
      <pre className={cn(contentClassName, 'break-words whitespace-pre-wrap')}>
        <code>{code}</code>
      </pre>
    );
  }

  return (
    <div
      className={contentClassName}
      dangerouslySetInnerHTML={{ __html: highlightedCode }}
    />
  );
}
