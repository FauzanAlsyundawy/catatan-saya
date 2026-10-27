import re
import uuid
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Sanitize filename against path traversal and forbidden chars."""
    clean = Path(name).name
    clean = re.sub(r"[\x00-\x1f\x7f]", "", clean)
    clean = clean.replace("..", "").replace("/", "").replace("\\", "").strip()
    if not clean:
        clean = "unnamed_file"
    return clean


def get_file_extension(filename: str) -> str:
    """Return lowercase extension including leading dot, e.g. '.docx'."""
    ext = Path(filename).suffix.lower()
    return ext


def format_file_size(size_bytes: int) -> str:
    """Human readable file size in B, KB, MB, GB."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def resolve_duplicate_filename(
    existing_names: set[str], original_filename: str
) -> str:
    """If original_filename already exists, append suffix (1), (2)."""
    if original_filename not in existing_names:
        return original_filename

    path = Path(original_filename)
    stem = path.stem
    ext = path.suffix

    match = re.search(r"^(.*?)\s*\((\d+)\)$", stem)
    if match:
        base_stem = match.group(1).strip()
        start_counter = int(match.group(2)) + 1
    else:
        base_stem = stem
        start_counter = 1

    counter = start_counter
    while True:
        candidate = f"{base_stem} ({counter}){ext}"
        if candidate not in existing_names:
            return candidate
        counter += 1


def generate_stored_filename(original_filename: str) -> str:
    """Generate a random UUID filename preserving lowercase extension."""
    ext = get_file_extension(original_filename)
    return f"{uuid.uuid4().hex}{ext}"


_EXT_ICON_MAP: dict[str, str] = {
    ".doc": "file-text",
    ".docx": "file-text",
    ".xls": "table-2",
    ".xlsx": "table-2",
    ".csv": "table-2",
    ".txt": "file-code",
    ".log": "file-code",
    ".md": "file-code",
    ".ini": "file-code",
    ".conf": "file-code",
    ".cfg": "file-code",
    ".json": "code",
    ".xml": "code",
    ".yml": "code",
    ".pdf": "file-check",
    ".ppt": "presentation",
    ".pptx": "presentation",
    ".pkt": "network",
    ".pka": "network",
    ".zip": "archive",
    ".png": "image",
    ".jpg": "image",
}


def get_file_icon(extension: str) -> str:
    """Return Lucide icon name based on file extension."""
    return _EXT_ICON_MAP.get(extension.lower(), "file")
