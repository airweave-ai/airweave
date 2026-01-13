import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SyncProgressIndicator } from "./SyncProgressIndicator";
import type { SyncProgressUpdate } from "../lib/types";

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

    expect(screen.getByText("160 synced")).toBeInTheDocument();
  });

  it("shows inserted count in green when present", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 42,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText("+42")).toBeInTheDocument();
  });

  it("shows updated count when present", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_updated: 15,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText("~15")).toBeInTheDocument();
  });

  it("shows deleted count in red when present", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_deleted: 5,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText("-5")).toBeInTheDocument();
  });

  it("hides zero counts", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 10,
      entities_updated: 0,
      entities_deleted: 0,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText("+10")).toBeInTheDocument();
    expect(screen.queryByText("~0")).not.toBeInTheDocument();
    expect(screen.queryByText("-0")).not.toBeInTheDocument();
  });

  it("formats large numbers with locale separators", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 1234567,
    };

    render(<SyncProgressIndicator progress={progress} />);

    // The exact format depends on locale, but it should be formatted
    expect(screen.getByText(/1,234,567 synced/)).toBeInTheDocument();
    expect(screen.getByText(/\+1,234,567/)).toBeInTheDocument();
  });

  it("renders progress bar element", () => {
    render(<SyncProgressIndicator progress={baseProgress} />);

    // Check for progress bar container
    const progressBar = document.querySelector(".animate-progress-indeterminate");
    expect(progressBar).toBeInTheDocument();
  });

  it("shows all count types together", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 100,
      entities_updated: 25,
      entities_deleted: 3,
      entities_kept: 500,
      entities_skipped: 2,
    };

    render(<SyncProgressIndicator progress={progress} />);

    // Total = 100 + 25 + 3 + 500 + 2 = 630
    expect(screen.getByText("630 synced")).toBeInTheDocument();
    expect(screen.getByText("+100")).toBeInTheDocument();
    expect(screen.getByText("~25")).toBeInTheDocument();
    expect(screen.getByText("-3")).toBeInTheDocument();
  });
});
