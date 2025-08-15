#
# emoji_matrix.py
#
"""
Pyvider Telemetry Emoji Matrix and Display Utilities.
Defines the legacy DAS emoji mappings and provides utilities to display
active emoji configurations (legacy or layer-based).
"""
import os

from pyvider.telemetry.logger import (
    base as pyvider_logger_base,  # For accessing the global logger instance
)

# Import types for resolved config structure
from pyvider.telemetry.types import CustomDasEmojiSet, SemanticFieldDefinition

PRIMARY_EMOJI: dict[str, str] = {
    "system": "⚙️", "server": "🛎️", "client": "🙋", "network": "🌐",
    "security": "🔐", "config": "🔩", "database": "🗄️", "cache": "💾",
    "task": "🔄", "plugin": "🔌", "telemetry": "🛰️", "di": "💉",
    "protocol": "📡", "file": "📄", "user": "👤", "test": "🧪",
    "utils": "🧰", "core": "🌟", "auth": "🔑", "entity": "🦎",
    "report": "📈", "payment": "💳",
    "default": "❓",
}

SECONDARY_EMOJI: dict[str, str] = {
    "init": "🌱", "start": "🚀", "stop": "🛑", "connect": "🔗",
    "disconnect": "💔", "listen": "👂", "send": "📤", "receive": "📥",
    "read": "📖", "write": "📝", "process": "⚙️", "validate": "🛡️",
    "execute": "▶️", "query": "🔍", "update": "🔄", "delete": "🗑️",
    "login": "➡️", "logout": "⬅️", "auth": "🔑", "error": "🔥",
    "encrypt": "🛡️", "decrypt": "🔓", "parse": "🧩", "transmit": "📡",
    "build": "🏗️", "schedule": "📅", "emit": "📢", "load": "💡",
    "observe": "🧐", "request": "🗣️", "interrupt": "🚦",
    "register": "⚙️",
    "default": "❓",
}

TERTIARY_EMOJI: dict[str, str] = {
    "success": "✅", "failure": "❌", "error": "🔥", "warning": "⚠️",
    "info": "ℹ️", "debug": "🐞", "trace": "👣", "attempt": "⏳",
    "retry": "🔁", "skip": "⏭️", "complete": "🏁", "timeout": "⏱️",
    "notfound": "❓", "unauthorized": "🚫", "invalid": "💢", "cached": "🎯",
    "ongoing": "🏃", "idle": "💤", "ready": "👍",
    "default": "➡️",
}

def _format_emoji_set_for_display(emoji_set: CustomDasEmojiSet) -> list[str]:
    lines = [f"  Emoji Set: '{emoji_set.name}' (Default Key: '{emoji_set.default_emoji_key}')"]
    for key, emoji in sorted(emoji_set.emojis.items()):
        lines.append(f"    {emoji}  -> {key.capitalize()}")
    return lines

def _format_field_definition_for_display(field_def: SemanticFieldDefinition) -> str:
    parts = [f"  Log Key: '{field_def.log_key}'"]
    if field_def.description:
        parts.append(f"    Desc: {field_def.description}")
    if field_def.value_type:
        parts.append(f"    Type: {field_def.value_type}")
    if field_def.emoji_set_name:
        parts.append(f"    Emoji Set: '{field_def.emoji_set_name}'")
        if field_def.default_emoji_override_key:
            parts.append(f"    Default Emoji Key (Override): '{field_def.default_emoji_override_key}'")
    return "\n".join(parts)


def show_emoji_matrix() -> None: # pragma: no cover
    """
    Prints the active Pyvider emoji logging contract to the console.
    If semantic layers are active, it displays their configuration.
    Otherwise, it displays the legacy DAS emoji mappings.
    Activated by `PYVIDER_SHOW_EMOJI_MATRIX` environment variable.
    """
    if os.getenv("PYVIDER_SHOW_EMOJI_MATRIX", "false").strip().lower() not in ("true", "1", "yes"):
        return

    matrix_logger = pyvider_logger_base.logger.get_logger("pyvider.telemetry.emoji_matrix_display")

    # Access the resolved semantic config from the global logger instance
    # This assumes the logger has been configured (explicitly or lazily)
    pyvider_logger_base.logger._ensure_configured() # Ensure config is loaded
    resolved_config_tuple = getattr(pyvider_logger_base.logger, '_active_resolved_semantic_config', None)

    lines: list[str] = []

    if resolved_config_tuple:
        resolved_field_definitions, resolved_emoji_sets_lookup = resolved_config_tuple

        if resolved_field_definitions: # New semantic layers are active
            lines.append("Pyvider Telemetry: Active Semantic Layer Emoji Contract")
            lines.append("="*70)
            lines.append("Active Semantic Field Definitions (Order determines prefix sequence):")
            if not resolved_field_definitions:
                lines.append("  (No semantic field definitions are active)")
            for i, field_def in enumerate(resolved_field_definitions):
                lines.append(f"\nField {i+1}:")
                lines.append(_format_field_definition_for_display(field_def))

            lines.append("\n" + "="*70)
            lines.append("Available Emoji Sets (Referenced by Semantic Field Definitions):")
            if not resolved_emoji_sets_lookup:
                lines.append("  (No emoji sets are defined/active)")
            for set_name in sorted(resolved_emoji_sets_lookup.keys()):
                emoji_set = resolved_emoji_sets_lookup[set_name]
                lines.extend(_format_emoji_set_for_display(emoji_set))
                lines.append("") # Spacer

        else: # No custom fields resolved, means legacy DAS is active
            lines.append("Pyvider Telemetry: Legacy DAS Emoji Contract (No custom layers active)")
            lines.append("="*70)
            lines.append("Primary Emojis (Legacy 'domain' key):")
            lines.extend(f"  {e}  -> {k.capitalize()}" for k, e in PRIMARY_EMOJI.items())
            lines.append("\nSecondary Emojis (Legacy 'action' key):")
            lines.extend(f"  {e}  -> {k.capitalize()}" for k, e in SECONDARY_EMOJI.items())
            lines.append("\nTertiary Emojis (Legacy 'status' key):")
            lines.extend(f"  {e}  -> {k.capitalize()}" for k, e in TERTIARY_EMOJI.items())
    else:
        lines.append("Pyvider Telemetry: Emoji configuration not yet resolved or available.")


    if lines:
        matrix_logger.info("\n".join(lines))
    else: # Should not happen if _ensure_configured works
        matrix_logger.warning("Could not determine active emoji configuration to display.")


# 💡🧱
