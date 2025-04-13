# Fern Module

This directory contains the Fern API definition and configuration for Airweave's API documentation and SDK generation.

## Structure

```
fern/
├── definition/     # API definition files including overrides
├── openapi/       # OpenAPI specification files
├── docs/          # Documentation assets
├── generate-local.sh   # Script for local SDK generation
├── generators.yml      # Fern generators configuration
├── fern.config.json    # Fern core configuration
└── docs.yml           # Documentation configuration
```

## Overrides

The `definition/overrides.yml` contains path configurations for endpoints that should be ignored in the API documentation and SDK generation. This includes:

- Health check endpoints
- API key management
- Chat functionality
- Cursor development endpoints
- DAG management endpoints

## Local Development

To generate SDKs locally, run:

```bash
./generate-local.sh
```

## Configuration

- `generators.yml`: Defines which SDKs and documentation to generate
- `fern.config.json`: Core Fern configuration settings
- `docs.yml`: Documentation generation settings
