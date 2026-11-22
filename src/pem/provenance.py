"""Portable metadata exports without workstation-specific absolute paths."""
from __future__ import annotations

from pathlib import Path


def portable_metadata(value, root: Path):
    """Relativize project paths and alias external paths throughout a JSON value.

    Workstation paths are needed for execution but not for published provenance.
    Preserve input hashes, software versions, measurements, and reference URLs.
    External aliases are consistent within an export and reveal no original name.
    """
    root = root.resolve()
    aliases = {}

    def label(text):
        if not isinstance(text, str):
            return text
        path = Path(text)
        if not path.is_absolute():
            return text
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            if text not in aliases:
                suffix = path.suffix
                suffix = suffix if suffix in {".csv", ".json", ".txt", ".py", ".pdf"} else ""
                aliases[text] = f"external/input_{len(aliases) + 1}{suffix}"
            return aliases[text]

    def visit(item):
        if isinstance(item, dict):
            result = {}
            for key, content in item.items():
                public_key = label(key)
                if public_key in result:
                    raise ValueError("Metadata keys collide after path normalization")
                result[public_key] = visit(content)
            return result
        if isinstance(item, (list, tuple)):
            return [visit(content) for content in item]
        return label(item)

    return visit(value)
