#
# __init__.py
#
"""
Pyvider Telemetry Logger Sub-package.
Re-exports key components related to logging functionality.
"""
from pyvider.telemetry.logger.base import (
    PyviderLogger,  # Class definition
    logger,  # Global instance
)
from pyvider.telemetry.logger.emoji_matrix import (
    PRIMARY_EMOJI,  # Legacy/default domain emojis
    SECONDARY_EMOJI,  # Legacy/default action emojis
    TERTIARY_EMOJI,  # Legacy/default status emojis
    show_emoji_matrix,  # Utility to display emoji configurations
)

__all__ = [
    "PRIMARY_EMOJI",
    "SECONDARY_EMOJI",
    "TERTIARY_EMOJI",
    "PyviderLogger",
    "logger",
    "show_emoji_matrix",
]

# 🐍📝
