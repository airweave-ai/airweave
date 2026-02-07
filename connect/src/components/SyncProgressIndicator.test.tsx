import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SyncProgressIndicator } from "./SyncProgressIndicator";
import type { SyncProgressUpdate } from "../lib/types";

/**
 * NumberFlow renders numbers in a shadow DOM structure that splits text across elements.
 * This helper finds text by checking the full textContent of elements.
 */
function getByTextContent(text: string | RegExp) {
  return screen.getByText((_, element) => {
    if (!element) return false;
    const hasText =
      typeof text === "string"
        ? element.textContent === text
        : text.test(element.textContent || "");
    // Only match if this element directly contains the text (not a parent)
    const childrenDontMatch = Array.from(element.children).every((child) =>
      typeof text === "string"
        ? child.textContent !== text
        : !text.test(child.textContent || ""),
    );
    return hasText && childrenDontMatch;
  });
}

describe("SyncProgressIndicator", () => {
  const baseProgress: SyncProgressUpdate = {
    entities_inserted: 0,
    entities_updated: 0,
    entities_deleted: 0,
    entities_kept: 0,
    entities_skipped: 0,
    entities_encountered: {},
  };

  it("renders total synced count", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 50,
      entities_updated: 10,
      entities_kept: 100,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(getByTextContent("160 synced")).toBeInTheDocument();
  });

  it("shows checkmark when sync is complete", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 50,
      is_complete: true,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(getByTextContent("50 synced")).toBeInTheDocument();
  });

  it("formats large numbers with locale separators", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 1234567,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(getByTextContent(/1,234,567 synced/)).toBeInTheDocument();
  });

  it("renders spinning loader icon", () => {
    render(<SyncProgressIndicator progress={baseProgress} />);

    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("excludes deleted entities from total", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 100,
      entities_updated: 25,
      entities_deleted: 3,
      entities_kept: 500,
      entities_skipped: 2,
    };

    render(<SyncProgressIndicator progress={progress} />);

    // Total = 100 + 25 + 500 + 2 = 627 (deleted not included)
    expect(getByTextContent("627 synced")).toBeInTheDocument();
  });

  it("renders error state when sync has failed", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 50,
      is_failed: true,
      error: "Connection timed out",
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText("Connection timed out")).toBeInTheDocument();
    // Should not show spinner or synced count
    expect(document.querySelector(".animate-spin")).not.toBeInTheDocument();
  });

  it("renders default error message when no error text provided", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      is_failed: true,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText("Sync failed")).toBeInTheDocument();
  });

  it("renders error icon in error state", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      is_failed: true,
      error: "API error",
    };

    const { container } = render(<SyncProgressIndicator progress={progress} />);

    // AlertCircle icon should be present (lucide-react renders as svg)
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders reconnecting state when isReconnecting is true", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 50,
    };

    render(<SyncProgressIndicator progress={progress} isReconnecting={true} />);

    expect(screen.getByText("Reconnecting...")).toBeInTheDocument();
    // Should not show synced count or spinner when reconnecting
    expect(document.querySelector(".animate-spin")).not.toBeInTheDocument();
  });

  it("renders pulsing icon in reconnecting state", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
    };

    const { container } = render(
      <SyncProgressIndicator progress={progress} isReconnecting={true} />,
    );

    // WifiOff icon should be present with animate-pulse class
    const pulsingIcon = container.querySelector(".animate-pulse");
    expect(pulsingIcon).toBeInTheDocument();
  });

  it("prioritizes error state over reconnecting state", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      is_failed: true,
      error: "Connection lost",
    };

    render(<SyncProgressIndicator progress={progress} isReconnecting={true} />);

    // Error state should take precedence
    expect(screen.getByText("Connection lost")).toBeInTheDocument();
    expect(screen.queryByText("Reconnecting...")).not.toBeInTheDocument();
  });
});
