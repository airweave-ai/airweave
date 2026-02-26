"""Utility functions for determining file types from MIME types.

This module provides general utilities and helpers for the various entities.
"""

from typing import Optional


def _determine_file_type_from_mime(mime_type: Optional[str]) -> str:
    """Determine file type from MIME type.

    Args:
        mime_type: The MIME type of the file

    Returns:
        A string representing the file type category
    """
    if not mime_type:
        return "unknown"

    mime_type = mime_type.lower()

    # Direct MIME type mappings
    mime_mappings = {
        # Google Workspace files
        "application/vnd.google-apps.document": "google_doc",
        "application/vnd.google-apps.spreadsheet": "google_sheets",
        "application/vnd.google-apps.presentation": "google_slides",
        "application/vnd.google-apps.form": "google_forms",
        "application/vnd.google-apps.drawing": "google_drawings",
        "application/vnd.google-apps.script": "google_apps_script",
        "application/vnd.google-apps.site": "google_sites",
        "application/vnd.google-apps.folder": "folder",
        "application/vnd.google-apps.jam": "google_jamboard",
        "application/vnd.google-apps.map": "google_my_maps",
        "application/vnd.google-apps.vid": "google_vids",
        # Microsoft Office files
        "application/msword": "microsoft_word_doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
            "microsoft_word_doc"
        ),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.template": (
            "microsoft_word_template"
        ),
        "application/vnd.ms-word.document.macroenabled.12": "microsoft_word_macro_doc",
        "application/vnd.ms-excel": "microsoft_excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "microsoft_excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.template": (
            "microsoft_excel_template"
        ),
        "application/vnd.ms-excel.sheet.macroenabled.12": "microsoft_excel_macro",
        "application/vnd.ms-powerpoint": "microsoft_powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
            "microsoft_powerpoint"
        ),
        "application/vnd.openxmlformats-officedocument.presentationml.template": (
            "microsoft_powerpoint_template"
        ),
        "application/vnd.ms-powerpoint.presentation.macroenabled.12": "microsoft_powerpoint_macro",
        # Document formats
        "application/pdf": "pdf",
        "text/plain": "text",
        "text/html": "html",
        "text/xml": "xml",
        "application/xml": "xml",
        "application/json": "json",
        "text/markdown": "markdown",
        "application/rtf": "rtf",
        # Archive formats
        "application/zip": "zip",
        "application/x-rar-compressed": "rar",
        "application/vnd.rar": "rar",
        "application/x-tar": "tar",
        "application/gzip": "gzip",
        "application/x-7z-compressed": "7zip",
        # Code and development files
        "text/javascript": "javascript",
        "application/javascript": "javascript",
        "text/css": "css",
        "application/x-python-code": "python",
        "text/x-python": "python",
        "text/x-java-source": "java",
        "text/x-c": "c_code",
        "text/x-c++src": "cpp_code",
        "application/x-sh": "shell_script",
    }

    # Check direct mappings first
    if mime_type in mime_mappings:
        return mime_mappings[mime_type]

    # Handle pattern-based mappings
    return _handle_pattern_based_types(mime_type)


def _handle_pattern_based_types(mime_type: str) -> str:
    """Handle MIME types that require pattern matching.

    Args:
        mime_type: The lowercase MIME type string

    Returns:
        A string representing the file type category
    """
    # Image formats
    if mime_type.startswith("image/"):
        return _determine_image_type(mime_type)

    # Video formats
    if mime_type.startswith("video/"):
        return _determine_video_type(mime_type)

    # Audio formats
    if mime_type.startswith("audio/"):
        return _determine_audio_type(mime_type)

    # Font formats
    if mime_type.startswith("font/") or "font" in mime_type:
        return "font"

    # Fallback categories
    if mime_type.startswith("text/"):
        return "text"
    if mime_type.startswith("application/"):
        return "application"

    return "unknown"


def _determine_image_type(mime_type: str) -> str:
    """Determine specific image type from MIME type."""
    if "jpeg" in mime_type or "jpg" in mime_type:
        return "image_jpeg"
    elif "png" in mime_type:
        return "image_png"
    elif "gif" in mime_type:
        return "image_gif"
    elif "svg" in mime_type:
        return "image_svg"
    elif "bmp" in mime_type:
        return "image_bmp"
    elif "webp" in mime_type:
        return "image_webp"
    elif "tiff" in mime_type:
        return "image_tiff"
    else:
        return "image"


def _determine_video_type(mime_type: str) -> str:
    """Determine specific video type from MIME type."""
    if "mp4" in mime_type:
        return "video_mp4"
    elif "avi" in mime_type:
        return "video_avi"
    elif "mov" in mime_type or "quicktime" in mime_type:
        return "video_mov"
    elif "wmv" in mime_type:
        return "video_wmv"
    elif "webm" in mime_type:
        return "video_webm"
    else:
        return "video"


def _determine_audio_type(mime_type: str) -> str:
    """Determine specific audio type from MIME type."""
    if "mp3" in mime_type or "mpeg" in mime_type:
        return "audio_mp3"
    elif "wav" in mime_type:
        return "audio_wav"
    elif "ogg" in mime_type:
        return "audio_ogg"
    elif "aac" in mime_type:
        return "audio_aac"
    else:
        return "audio"
