import type { ReactNode } from "react";
import { PoweredByAirweave } from "./PoweredByAirweave";

interface PageLayoutProps {
  title: string;
  headerRight?: ReactNode;
  headerLeft?: ReactNode;
  children: ReactNode;
  centerContent?: boolean;
}

export function PageLayout({
  title,
  headerRight,
  headerLeft,
  children,
  centerContent = false,
}: PageLayoutProps) {
  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      <header className="flex-shrink-0 p-6 pb-4">
        <div className="flex items-center gap-3">
          {headerLeft}
          <div className="flex-1 flex items-center justify-between">
            <h1
              className="font-medium text-lg"
              style={{ color: "var(--connect-text)" }}
            >
              {title}
            </h1>
            {headerRight}
          </div>
        </div>
      </header>

      <main
        className={`flex-1 overflow-y-auto px-6 scrollable-content ${
          centerContent ? "flex flex-col items-center justify-center text-center" : ""
        }`}
      >
        {children}
      </main>

      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
