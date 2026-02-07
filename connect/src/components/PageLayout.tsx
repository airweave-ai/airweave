import type { ReactNode } from "react";
import { PoweredByAirweave } from "./PoweredByAirweave";

interface PageLayoutProps {
  title?: string;
  headerRight?: ReactNode;
  headerLeft?: ReactNode;
  footerContent?: ReactNode;
  children: ReactNode;
  centerContent?: boolean;
  hideHeader?: boolean;
}

export function PageLayout({
  title,
  headerRight,
  headerLeft,
  footerContent,
  children,
  centerContent = false,
  hideHeader = false,
}: PageLayoutProps) {
  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      {!hideHeader && (
        <header className="flex-shrink-0 p-6 pb-4">
          <div className="flex items-center gap-3">
            {headerLeft}
            <div className="flex-1 flex items-center justify-between">
              {title && (
                <h1
                  className="font-medium text-lg"
                  style={{
                    color: "var(--connect-text)",
                    fontFamily: "var(--connect-font-heading)",
                  }}
                >
                  {title}
                </h1>
              )}
              {headerRight}
            </div>
          </div>
        </header>
      )}

      <main
        className={`flex-1 overflow-y-auto px-6 ${
          hideHeader ? "" : "scrollable-content"
        } ${centerContent ? "flex flex-col items-center justify-center text-center" : ""}`}
      >
        {children}
      </main>

      {footerContent && (
        <div
          className="flex-shrink-0 px-6 pt-4 border-t"
          style={{
            backgroundColor: "var(--connect-bg)",
            borderColor: "var(--connect-border)",
          }}
        >
          {footerContent}
        </div>
      )}

      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
