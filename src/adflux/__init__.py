"""adflux: pure-Python Markdown ↔ Atlassian Document Format (ADF) converter."""

from adflux.api import convert, inspect_ast, list_formats, validate
from adflux.errors import (
    AdfluxError,
    InvalidADFError,
    MappingError,
    UnrepresentableNodeError,
    UnsupportedFormatError,
)
from adflux.options import Options, get_registry

__version__ = "0.1.0"

__all__ = [
    "AdfluxError",
    "InvalidADFError",
    "MappingError",
    "Options",
    "UnrepresentableNodeError",
    "UnsupportedFormatError",
    "__version__",
    "convert",
    "get_registry",
    "inspect_ast",
    "list_formats",
    "validate",
]
