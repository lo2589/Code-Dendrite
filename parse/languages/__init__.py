"""Unified language discovery and parsing entry points."""

from parse.languages.pipeline import ParsedAnchor, parse_paths, walk_source_paths
from parse.languages.registry import LanguageSpec, language_for_path, supported_extensions

__all__ = [
    "LanguageSpec", "ParsedAnchor", "language_for_path", "parse_paths",
    "supported_extensions", "walk_source_paths",
]
