"""Shared file type constants for sync operations.

Single source of truth for supported file types across downloader and pipeline.
"""

# Extensions we support for conversion and processing
# Extracted from entity_pipeline.py converter_map to ensure consistency
SUPPORTED_FILE_EXTENSIONS = {
    # Documents (Mistral OCR)
    ".pdf",
    ".docx",
    ".pptx",
    # Images (Mistral OCR)
    ".jpg",
    ".jpeg",
    ".png",
    # HTML
    ".html",
    ".htm",
    # Text files
    ".txt",
    ".json",
    ".xml",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    # Code files (tree-sitter AST chunking)
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
