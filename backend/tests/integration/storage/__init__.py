"""Storage backend integration tests.

These tests run against real cloud infrastructure:
- AWS S3: airweave-storage-backend-tests bucket
- GCP GCS: airweave-storage-backend-tests bucket
- Azure Blob: backend-tests container in airweavecoredevstorage

Tests use unique prefixes for isolation and clean up after themselves.
"""
