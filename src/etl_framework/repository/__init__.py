"""Metadata repository — loads, validates, indexes EntitySpec/SourceSpec docs."""

from .validation import ValidationError, ValidationIssue, validate_repository
from .yaml_repo import MetadataRepository

__all__ = ["MetadataRepository", "ValidationError", "ValidationIssue", "validate_repository"]
