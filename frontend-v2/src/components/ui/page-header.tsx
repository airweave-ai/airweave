import { HelpCircle } from "lucide-react";
import * as React from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type PageHeaderContent = {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
};

type PageHeaderContextProps = {
  content: PageHeaderContent;
  setContent: (content: PageHeaderContent) => void;
};

const PageHeaderContext = React.createContext<PageHeaderContextProps | null>(
  null
);

function usePageHeaderContext() {
  const context = React.useContext(PageHeaderContext);
  if (!context) {
    throw new Error(
      "usePageHeaderContext must be used within a PageHeaderProvider."
    );
  }
  return context;
}

/**
 * Hook for route components to register their page header content.
 * Content is automatically cleared when the component unmounts.
 */
function usePageHeader(content: PageHeaderContent) {
  const { setContent } = usePageHeaderContext();
  const contentRef = React.useRef(content);

  React.useLayoutEffect(() => {
    contentRef.current = content;
  });

  React.useEffect(() => {
    setContent(contentRef.current);
    return () => {
      setContent({});
    };
  }, [setContent]);
}

function PageHeaderProvider({ children }: { children: React.ReactNode }) {
  const [content, setContent] = React.useState<PageHeaderContent>({});

  const contextValue = React.useMemo<PageHeaderContextProps>(
    () => ({
      content,
      setContent,
    }),
    [content]
  );

  return (
    <PageHeaderContext.Provider value={contextValue}>
      {children}
    </PageHeaderContext.Provider>
  );
}

function PageHeaderContent() {
  const { content } = usePageHeaderContext();

  if (!content.title) {
    return null;
  }

  return (
    <div className="flex flex-1 items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-2">
        <h1 className="truncate font-mono text-sm font-medium uppercase">
          {content.title}
        </h1>
        {content.description && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground inline-flex items-center justify-center transition-colors"
              >
                <HelpCircle className="size-4" />
                <span className="sr-only">More info</span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              {content.description}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
      {content.actions && (
        <div className="flex shrink-0 items-center gap-2">
          {content.actions}
        </div>
      )}
    </div>
  );
}

export {
  PageHeaderContent,
  PageHeaderProvider,
  usePageHeader,
  usePageHeaderContext,
  type PageHeaderContent as PageHeaderContentType,
};
