"""Constants for the connector documentation generator."""

from pathlib import Path

# Define paths
REPO_ROOT = Path(__file__).parent.parent.parent.parent
FRONTEND_ICONS_DIR = REPO_ROOT / "frontend" / "src" / "components" / "icons" / "apps"
BACKEND_ENTITIES_DIR = REPO_ROOT / "backend" / "airweave" / "platform" / "entities"
BACKEND_SOURCES_DIR = REPO_ROOT / "backend" / "airweave" / "platform" / "sources"
DOCS_CONNECTORS_DIR = REPO_ROOT / "fern" / "docs" / "pages" / "connectors"
AUTH_CONFIG_PATH = REPO_ROOT / "backend" / "airweave" / "platform" / "configs" / "auth.py"
DOCS_YML_PATH = REPO_ROOT / "fern" / "docs.yml"

# Define auth type descriptions for documentation
AUTH_TYPE_DESCRIPTIONS = {
    "oauth2": "OAuth 2.0 authentication flow",
    "oauth2_with_refresh": "OAuth 2.0 with refresh token",
    "oauth2_with_refresh_rotating": "OAuth 2.0 with rotating refresh token",
    "api_key": "API key authentication",
    "config_class": "Configuration-based authentication",
    "none": "No authentication required",
    "native_functionality": "Native functionality",
    "url_and_api_key": "URL and API key authentication",
}

# Auto-generated content markers
CONTENT_START_MARKER = "{/* AUTO-GENERATED CONTENT START */}"
CONTENT_END_MARKER = "{/* AUTO-GENERATED CONTENT END */}"
