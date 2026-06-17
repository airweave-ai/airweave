#!/usr/bin/env bash
# Run mypy across the airweave package and fail only on violations that
# land on lines changed vs. the merge base with origin/main. Mirrors the
# `mypy (changed lines)` job in .github/workflows/code-quality.yml so the
# pre-commit gate matches the CI gate.
#
# Why this shape: mypy needs the whole import graph to type-check anything,
# so we always run it on the full package. diff-quality then filters the
# report down to lines the current diff touches — the same standard CI uses.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/backend"

COMPARE_BRANCH="${MYPY_DIFF_BASE:-origin/main}"

# If origin/main isn't fetched (fresh shallow clone, offline), fall back
# to local main, and as a last resort skip the diff gate. We never want
# the hook to crash the commit because of git plumbing issues.
if ! git rev-parse --verify --quiet "$COMPARE_BRANCH" >/dev/null; then
  if git rev-parse --verify --quiet main >/dev/null; then
    COMPARE_BRANCH="main"
  else
    echo "mypy_diff: no origin/main or main ref available; skipping diff-quality gate." >&2
    exit 0
  fi
fi

REPORT="$(mktemp -t mypy_report.XXXXXX.txt)"
trap 'rm -f "$REPORT"' EXIT

# Full-package mypy — never fails this step; we always want to feed the
# report into diff-quality below.
poetry run mypy --config-file pyproject.toml airweave/ > "$REPORT" || true

poetry run diff-quality \
  --violations=mypy \
  --compare-branch="$COMPARE_BRANCH" \
  --fail-under=100 \
  "$REPORT"
