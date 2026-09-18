"""
File validation utilities.

Content-sniff uploaded files by magic bytes, not just extension.
Enforce max size and allowed formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Set

# Magic byte signatures
IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"BM": "image/bmp",
    b"RIFF": "image/webp",  # WebP starts with RIFF....WEBP
}

VIDEO_SIGNATURES = {
    b"\x00\x00\x00\x18ftypmp4": "video/mp4",
    b"\x00\x00\x00\x1cftypmp4": "video/mp4",
    b"\x00\x00\x00\x20ftypmp4": "video/mp4",
    b"\x00\x00\x00": "video/mp4",  # generic ftyp
    b"RIFF": "video/avi",
    b"\x1a\x45\xdf\xa3": "video/mkv",
}

ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}


def validate_image_file(
    content: bytes,
    filename: str,
    max_size: int = 50 * 1024 * 1024,
) -> tuple[bool, str]:
    """
    Validate an uploaded image file.

    Returns (is_valid, error_message).
    """
    if len(content) > max_size:
        return False, f"File too large ({len(content)} bytes, max {max_size})"

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"Invalid extension: {ext}. Allowed: {ALLOWED_IMAGE_EXTENSIONS}"

    # Content sniffing
    is_valid_content = any(content.startswith(sig) for sig in IMAGE_SIGNATURES)
    if not is_valid_content:
        return False, "File content does not match any known image format"

    return True, ""


def validate_video_file(
    content: bytes,
    filename: str,
    max_size: int = 50 * 1024 * 1024,
) -> tuple[bool, str]:
    """
    Validate an uploaded video file.

    Returns (is_valid, error_message).
    """
    if len(content) > max_size:
        return False, f"File too large ({len(content)} bytes, max {max_size})"

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        return False, f"Invalid extension: {ext}. Allowed: {ALLOWED_VIDEO_EXTENSIONS}"

    return True, ""
