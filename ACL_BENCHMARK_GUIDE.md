# SharePoint 2019 ACL Benchmark & Testing Guide

This guide explains how to run ACL sync performance benchmarks with 50K users and correctness tests.

## Prerequisites

- Docker Compose running (`docker compose -f docker/docker-compose.dev.yml up -d`)
- Backend running (`poetry run python -m uvicorn airweave.main:app --reload --port 8001`)
- Temporal worker running (`poetry run python -m airweave.temporal.worker`)
- Access to SharePoint 2019 VM (sharepoint-2019.demos.airweave.ai)
- Access to AD server (108.143.169.156)

## Quick Reference

| Test Type | Purpose | Data Scale | Duration |
|-----------|---------|------------|----------|
| Performance Benchmark | Measure ACL sync timing | 50K users, ~150K memberships | ~60-80 min |
| Test 4 (Static) | Verify ACL correctness | ~100 users | ~1-2 min |
| Test 5 (Incremental) | Verify change detection | ~100 users | ~5-10 min |

---

## 1. Performance Benchmark (50K Users)

### Data Already Generated

The 50K user dataset has already been generated in AD and SharePoint:
- **50,000 AD users** (regular, managers, executives, contractors, service accounts)
- **~5,000 AD groups** (hierarchical: root → division → department → team → project → pod)
- **~150,000 AD memberships** (users in groups, groups in groups)
- **1,000 SharePoint groups**

### Running the Benchmark

```bash
cd /Users/daanmanneke/Repositories/airweave-mistral/backend

# Ensure these settings in sharepoint2019_test.py:
#   FORCE_RESYNC = True
#   RUN_STATIC_TESTS = False
#   RUN_INCREMENTAL_TESTS = False

poetry run python ../sharepoint2019_test.py
```

### What to Look For

Monitor the worker terminal for Phase 2.5 timing:
```
Phase 2.5: Processing access control memberships
  ACL memberships upserted: X
  Duplicates skipped: Y
  Time: Z seconds
```

### Expected Results (Baseline)

| Scale | ACL Memberships | Phase 2.5 Time |
|-------|-----------------|----------------|
| 1K users | ~2,463 | ~44 seconds |
| 50K users | ~150,000 | ~30-45 minutes |

---

## 2. Test 4: Static ACL Verification

Tests that synced permissions in Airweave match the expected manifest.

### Setup (One-time)

```bash
cd /Users/daanmanneke/Repositories/infra-core/sharepoint-2019-trial/4-static-access-graph-tests/test-data-generator

# Create venv if not exists
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Generate Small Test Data (for correctness testing)

```bash
# This creates ~100 users with carefully defined permissions
python generate.py
```

### Run Verification

```bash
# First sync with small dataset
cd /Users/daanmanneke/Repositories/airweave-mistral/backend
poetry run python ../sharepoint2019_test.py  # with RUN_STATIC_TESTS = True

# Or run verify.py directly:
cd /Users/daanmanneke/Repositories/infra-core/sharepoint-2019-trial/4-static-access-graph-tests/test-data-generator
source venv/bin/activate
python verify.py \
    --manifest output/manifest.json \
    --airweave-url http://localhost:8001 \
    --collection-id <your-collection-id> \
    --destination vespa \
    --output output/metrics.json
```

---

## 3. Test 5: Incremental Change Tests

Tests that Airweave correctly detects and syncs permission changes.

### Setup (One-time)

```bash
cd /Users/daanmanneke/Repositories/infra-core/sharepoint-2019-trial/5-incremental-tests

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Tests

```bash
# Via sharepoint2019_test.py (recommended)
cd /Users/daanmanneke/Repositories/airweave-mistral/backend

# Set in sharepoint2019_test.py:
#   FORCE_RESYNC = False  # reuse existing collection
#   RUN_STATIC_TESTS = False
#   RUN_INCREMENTAL_TESTS = True
#   INCREMENTAL_TEST_MARKERS = None  # or "critical" for security tests only

poetry run python ../sharepoint2019_test.py
```

### Or Run Directly with Pytest

```bash
cd /Users/daanmanneke/Repositories/infra-core/sharepoint-2019-trial/5-incremental-tests
source venv/bin/activate

# Set environment variables
export COLLECTION_READABLE_ID=<your-collection-id>
export SOURCE_CONNECTION_ID=<your-source-connection-id>
export AIRWEAVE_API_URL=http://localhost:8001
# ... (see sharepoint2019_test.py for full list)

# Run all tests
pytest tests/ -v

# Run only security-critical tests
pytest tests/ -v -m critical
```

---

## 4. Regenerating Scale Data (if needed)

If you need to regenerate the 50K user dataset:

```bash
cd /Users/daanmanneke/Repositories/infra-core/sharepoint-2019-trial/4-static-access-graph-tests/test-data-generator
source venv/bin/activate

# Generate 50K users (~78 min total)
python generate_scale.py --users 50000

# Or a smaller scale for quick testing
python generate_scale.py --users 10000
```

### Generation Time Estimates

| Users | AD Groups | Memberships | Total Time |
|-------|-----------|-------------|------------|
| 1,000 | ~500 | ~3,000 | ~2 min |
| 10,000 | ~1,000 | ~30,000 | ~15 min |
| 50,000 | ~5,000 | ~150,000 | ~78 min |

---

## Configuration Reference

### sharepoint2019_test.py Settings

```python
# Benchmark mode (measure ACL sync performance)
FORCE_RESYNC = True
RUN_STATIC_TESTS = False
RUN_INCREMENTAL_TESTS = False

# Correctness mode (verify functionality)
FORCE_RESYNC = False  # or True for fresh sync
RUN_STATIC_TESTS = True
RUN_INCREMENTAL_TESTS = True
```

### Credentials (configured in sharepoint2019_test.py)

- SharePoint: `http://sharepoint-2019.demos.airweave.ai`
- AD Server: `ldaps://108.143.169.156:636`
- See `sharepoint2019_test.py` for usernames/passwords
