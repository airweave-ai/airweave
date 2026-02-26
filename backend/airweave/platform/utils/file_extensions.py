"""File extension utilities.

This module provides mappings and utilities for working with file extensions,
including language detection and binary file identification.
"""

import mimetypes
from pathlib import Path
from typing import Dict, Optional, Set

import chardet

# Default size limits
# Maximum file size to attempt text detection (10MB)
MAX_TEXT_DETECTION_SIZE = 10 * 1024 * 1024

# Maximum sample size for encoding detection (16KB)
ENCODING_SAMPLE_SIZE = 16 * 1024

# Minimum confidence threshold for encoding detection
MIN_ENCODING_CONFIDENCE = 0.8

# Minimum ratio of printable ASCII characters for text detection
MIN_ASCII_RATIO = 0.7

# Maximum sample size for ASCII ratio analysis
ASCII_SAMPLE_SIZE = 1000

# Mapping of file extensions to their full language names
LANGUAGE_MAP: Dict[str, str] = {
    # Web/Frontend
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".styl": "Stylus",
    ".js": "JavaScript",
    ".jsx": "JSX (JavaScript XML)",
    ".ts": "TypeScript",
    ".tsx": "TSX (TypeScript XML)",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    # Backend Languages
    ".py": "Python",
    ".rb": "Ruby",
    ".php": "PHP",
    ".java": "Java",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".d": "D",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir Script",
    ".erl": "Erlang",
    ".hrl": "Erlang Header",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".groovy": "Groovy",
    ".dart": "Dart",
    ".hs": "Haskell",
    ".lhs": "Literate Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml Interface",
    ".fs": "F#",
    ".fsx": "F# Script",
    ".nim": "Nim",
    ".cr": "Crystal",
    ".zig": "Zig",
    ".lua": "Lua",
    ".pl": "Perl",
    ".pm": "Perl Module",
    ".r": "R",
    ".vb": "Visual Basic",
    ".bas": "BASIC",
    # Shell/Scripting
    ".sh": "Shell",
    ".bash": "Bash",
    ".zsh": "Zsh",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell Module",
    ".psd1": "PowerShell Data",
    ".bat": "Batch",
    ".cmd": "Windows Command Script",
    ".coffee": "CoffeeScript",
    # Data/Config formats
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".cfg": "Configuration",
    ".conf": "Configuration",
    ".properties": "Properties",
    ".env": "Environment Variables",
    ".plist": "Property List",
    # Documentation
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".adoc": "AsciiDoc",
    ".asciidoc": "AsciiDoc",
    ".tex": "LaTeX",
    ".txt": "Plain Text",
    # Infrastructure
    ".tf": "Terraform",
    ".tfvars": "Terraform Variables",
    ".hcl": "HCL",
    ".dockerfile": "Dockerfile",
    ".jenkinsfile": "Jenkinsfile",
    # Database
    ".sql": "SQL",
    # Template Engines
    ".pug": "Pug",
    ".hbs": "Handlebars",
    ".twig": "Twig",
    ".njk": "Nunjucks",
    ".liquid": "Liquid",
    ".erb": "ERB",
    ".mustache": "Mustache",
    ".handlebars": "Handlebars",
    ".slim": "Slim",
    ".haml": "Haml",
    # GraphQL
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    # Proto
    ".proto": "Protocol Buffers",
    # Build Tools
    ".gradle": "Gradle",
    ".rake": "Rake",
    ".gyp": "GYP",
    ".make": "Makefile",
    ".mak": "Makefile",
    ".cmake": "CMake",
    # Other Dev Files
    ".diff": "Diff",
    ".patch": "Patch",
    ".gitignore": "Git Ignore",
    ".gitattributes": "Git Attributes",
    ".eslintrc": "ESLint Config",
    ".babelrc": "Babel Config",
    ".dockerignore": "Docker Ignore",
    ".editorconfig": "EditorConfig",
    # Lisp family
    ".scm": "Scheme",
    ".lisp": "Lisp",
    ".rkt": "Racket",
    # Miscellaneous
    ".cson": "CSON",
    ".cls": "Class File",
    ".pch": "Precompiled Header",
    ".lock": "Lock File",
    ".pp": "Puppet",
    ".kts": "Kotlin Script",
    ".f": "Fortran",
    ".f90": "Fortran 90",
    ".elm": "Elm",
    ".fsi": "F# Interface",
    ".jbuilder": "Jbuilder",
}

# Binary file extensions to exclude
BINARY_FILE_EXTENSIONS: Set[str] = {
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".jar",
    ".war",
    ".ear",
    # Executables and Libraries
    ".class",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".a",
    ".lib",
    ".out",
    # Data Files
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".psd",
    ".ai",
    ".xcf",
    ".tiff",
    ".heic",
    ".raw",
    ".cr2",
    ".nef",
    ".arw",
    ".rw2",
    ".orf",
    ".sr2",
    ".pef",
    ".raf",
    ".dcr",
    ".ptx",
    # Audio/Video
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".mkv",
    ".webm",
    ".m4v",
    ".aac",
    ".m4a",
    ".mid",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    # Python Specific
    ".pyc",
    ".pyo",
    # Object Files
    ".o",
    ".obj",
    # Mobile Applications
    ".apk",
    ".ipa",
    ".aab",
    # Installers
    ".deb",
    ".rpm",
    ".msi",
    # Web Assembly
    ".wasm",
    # E-books
    ".epub",
    ".mobi",
    # 3D Models
    ".blend",
    ".glb",
    ".gltf",
    ".fbx",
    ".3ds",
    ".max",
    ".dxf",
    ".3dm",
    ".3mf",
    ".stl",
    # Disk Images
    ".iso",
    ".dmg",
    # Package Formats
    ".whl",
    ".gem",
    # Certificates
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    # Databases
    ".mdb",
    ".accdb",
    # Flash
    ".swf",
    ".fla",
    # Compression
    ".xz",
    ".bz2",
    ".tgz",
    ".lz",
    ".lzma",
    ".lzo",
    ".z",
}


def is_likely_text_extension(extension: str) -> bool:
    """Check if a file extension is likely to be a text file based on known mappings.

    Args:
        extension: File extension including the dot (e.g., '.py')

    Returns:
        True if the extension is known to be a text file
    """
    return extension in LANGUAGE_MAP


def is_likely_binary_extension(extension: str) -> bool:
    """Check if a file extension is likely to be a binary file.

    Args:
        extension: File extension including the dot (e.g., '.exe')

    Returns:
        True if the extension is known to be a binary file
    """
    return extension in BINARY_FILE_EXTENSIONS


def get_language_for_extension(extension: str) -> str:
    """Get the programming language name for a file extension.

    Args:
        extension: File extension including the dot (e.g., '.py')

    Returns:
        The language name or 'Plain Text' if unknown
    """
    return LANGUAGE_MAP.get(extension, "Plain Text")


def is_text_by_content_analysis(content: bytes) -> bool:
    """Analyze if content is likely text based on encoding detection and character distribution.

    Args:
        content: Binary content to analyze

    Returns:
        True if the content is likely text, False otherwise
    """
    if not content:
        return False

    # Try to detect encoding, if it succeeds with high confidence, it's likely text
    detection = chardet.detect(content[:ENCODING_SAMPLE_SIZE])
    if (
        detection
        and detection["confidence"] > MIN_ENCODING_CONFIDENCE
        and detection["encoding"] is not None
    ):
        try:
            # Try to decode the content, if it succeeds it's likely text
            content[:ENCODING_SAMPLE_SIZE].decode(detection["encoding"], errors="strict")
            return True
        except UnicodeDecodeError:
            return False

    # Check for common binary sequences
    if b"\x00" in content[:ENCODING_SAMPLE_SIZE]:
        return False

    # Text files typically have a high ratio of printable ASCII characters
    sample = content[:ASCII_SAMPLE_SIZE] if len(content) > ASCII_SAMPLE_SIZE else content
    if not sample:
        return False

    ascii_count = sum(
        1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13)
    )  # printable + whitespace
    ascii_ratio = ascii_count / len(sample)

    return ascii_ratio > MIN_ASCII_RATIO


def is_text_file(path: str, size: int = 0, content: Optional[bytes] = None) -> bool:
    """Determine if a file is a text file based on extension, size, and content analysis.

    Args:
        path: File path or name
        size: File size in bytes (0 to skip size check)
        content: Optional sample of file content for analysis

    Returns:
        True if the file is likely a text file, False otherwise
    """
    # Skip large files
    if size > 0 and size > MAX_TEXT_DETECTION_SIZE:
        return False

    # Check extension
    ext = Path(path).suffix.lower()

    # Explicitly reject binary extensions
    if is_likely_binary_extension(ext):
        return False

    # Accept known text extensions
    if is_likely_text_extension(ext):
        return True

    # For unknown extensions, check content if available
    if content:
        return is_text_by_content_analysis(content)

    # For unknown extensions without content, use mimetypes as fallback
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type and mime_type.startswith("text/"):
        return True

    # Default to exclude files with unknown types
    return False
