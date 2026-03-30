"""Shared file type constants for sync operations.

Single source of truth for supported file types across downloader and pipeline.
"""

_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".pptx"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_HTML_EXTENSIONS = {".html", ".htm"}
_TEXT_EXTENSIONS = {".txt", ".json", ".xml", ".md", ".yaml", ".yml", ".toml"}
_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".kts",
    ".tf",
    ".tfvars",
}

SUPPORTED_FILE_EXTENSIONS = (
    _DOCUMENT_EXTENSIONS
    | _IMAGE_EXTENSIONS
    | _HTML_EXTENSIONS
    | _TEXT_EXTENSIONS
    | _CODE_EXTENSIONS
)
