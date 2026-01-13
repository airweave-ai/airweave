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

  it("includes baseCount in total", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 50,
    };

    render(<SyncProgressIndicator progress={progress} baseCount={200} />);

    expect(screen.getByText("250 synced")).toBeInTheDocument();
  });

  it("formats large numbers with locale separators", () => {
    const progress: SyncProgressUpdate = {
      ...baseProgress,
      entities_inserted: 1234567,
    };

    render(<SyncProgressIndicator progress={progress} />);

    expect(screen.getByText(/1,234,567 synced/)).toBeInTheDocument();
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
    expect(screen.getByText("627 synced")).toBeInTheDocument();
  });
});
