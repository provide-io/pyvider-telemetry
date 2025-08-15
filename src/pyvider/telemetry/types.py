# src/pyvider/telemetry/types.py
"""
Pyvider Telemetry Custom Type Definitions, Constants, and Data Structures.

This module centralizes custom type aliases, constants, and data structures
used throughout the `pyvider-telemetry` package.
"""
import logging as stdlib_logging
from typing import Literal

from attrs import define, field

# --- Core Log Level and Formatter Types ---
LogLevelStr = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE", "NOTSET"]
"""Type alias for valid log level strings, ensuring type safety for configuration."""

_VALID_LOG_LEVEL_TUPLE: tuple[LogLevelStr, ...] = (
    "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE", "NOTSET"
)
"""Tuple of all valid `LogLevelStr` values, used for runtime validation of log levels."""

ConsoleFormatterStr = Literal["key_value", "json"]
"""Type alias for console formatter choices, restricting options to supported formats."""

_VALID_FORMATTER_TUPLE: tuple[ConsoleFormatterStr, ...] = ("key_value", "json")
"""Tuple of all valid `ConsoleFormatterStr` values, used for runtime validation of formatters."""

# --- TRACE Level Constants ---
TRACE_LEVEL_NUM: int = 5 # Typically, DEBUG is 10, so TRACE is lower
"""Numeric value for the custom TRACE log level."""

TRACE_LEVEL_NAME: str = "TRACE"
"""String name for the custom TRACE log level."""

# Add TRACE to standard library logging if it doesn't exist
if not hasattr(stdlib_logging, TRACE_LEVEL_NAME): # pragma: no cover
    stdlib_logging.addLevelName(TRACE_LEVEL_NUM, TRACE_LEVEL_NAME)

    def trace(self: stdlib_logging.Logger, message: str, *args: object, **kwargs: object) -> None: # pragma: no cover
        if self.isEnabledFor(TRACE_LEVEL_NUM):
            self._log(TRACE_LEVEL_NUM, message, args, **kwargs) # type: ignore[arg-type]

    if not hasattr(stdlib_logging.Logger, "trace"): # pragma: no cover
        stdlib_logging.Logger.trace = trace # type: ignore[attr-defined]
    if stdlib_logging.root and not hasattr(stdlib_logging.root, "trace"): # pragma: no cover
         stdlib_logging.root.trace = trace.__get__(stdlib_logging.root, stdlib_logging.Logger) # type: ignore[attr-defined]


# --- Semantic Layering Data Structures ---

@define(frozen=True, slots=True)
class CustomDasEmojiSet:
    """A named set of emojis for a specific semantic category."""
    name: str = field() # e.g., "component_types", "llm_operations", "request_outcomes"
    emojis: dict[str, str] = field(factory=dict, converter=dict) # e.g., {"api": "🌐", "worker": "⚙️", "default": "🧩"}
    default_emoji_key: str = field(default="default") # The key within `emojis` to use as the default

@define(frozen=True, slots=True)
class SemanticFieldDefinition:
    """
    Defines a single semantic log key, its properties, and optional emoji mapping.
    """
    log_key: str = field() # e.g., "http.method", "llm.request.model"
    description: str | None = field(default=None)
    value_type: str | None = field(default=None) # e.g., "string", "integer", "iso_timestamp"
    emoji_set_name: str | None = field(default=None) # Optional: references a CustomDasEmojiSet.name
    default_emoji_override_key: str | None = field(default=None) # Optional: key within the emoji_set for this field's default

@define(frozen=True, slots=True)
class SemanticLayer:
    """
    Defines a semantic layer with its own emoji sets and field mappings.
    Layers provide conventions for structured logging in specific domains.
    """
    name: str = field() # e.g., "llm", "database", "http_client"
    description: str | None = field(default=None)
    emoji_sets: list[CustomDasEmojiSet] = field(factory=list)
    field_definitions: list[SemanticFieldDefinition] = field(factory=list)
    priority: int = field(default=0, converter=int) # Higher priority layers take precedence in case of conflicts
