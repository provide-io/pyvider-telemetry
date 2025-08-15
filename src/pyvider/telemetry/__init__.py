#
# __init__.py
#
"""
Pyvider Telemetry Library (structlog-based).
Primary public interface for the library, re-exporting common components.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pyvider-telemetry")
except PackageNotFoundError: # pragma: no cover
    __version__ = "0.0.0-dev"

from pyvider.telemetry.config import (
    LoggingConfig,
    TelemetryConfig,
)
from pyvider.telemetry.core import (
    setup_telemetry,
    shutdown_pyvider_telemetry,
)
from pyvider.telemetry.logger import logger  # Global logger instance
from pyvider.telemetry.logger.emoji_matrix import (
    PRIMARY_EMOJI,  # Legacy/default domain emojis
    SECONDARY_EMOJI,  # Legacy/default action emojis
    TERTIARY_EMOJI,  # Legacy/default status emojis
    show_emoji_matrix,  # Utility to display emoji configurations
)

# New type exports for semantic layering
from pyvider.telemetry.types import (
    ConsoleFormatterStr,
    CustomDasEmojiSet,
    LogLevelStr,
    SemanticFieldDefinition,
    SemanticLayer,
)

# New utility exports
from pyvider.telemetry.utils import timed_block

__all__ = [
    # Core setup and logger
    "logger",
    "setup_telemetry",
    "shutdown_pyvider_telemetry",
    # Configuration classes
    "TelemetryConfig",
    "LoggingConfig",
    # Type aliases
    "LogLevelStr",
    "ConsoleFormatterStr",
    # Legacy Emoji Dictionaries (still available for direct use or reference)
    "PRIMARY_EMOJI",
    "SECONDARY_EMOJI",
    "TERTIARY_EMOJI",
    # Semantic Layering classes
    "CustomDasEmojiSet",
    "SemanticFieldDefinition",
    "SemanticLayer",
    # Utilities
    "show_emoji_matrix",
    "timed_block",
    # Version
    "__version__",
]

# 🐍📝
