#
# config.py
#
"""
Pyvider Telemetry Configuration Module.
Defines data models for telemetry and logging settings, environment variable parsing,
and helpers for assembling structlog processor chains based on active configuration,
now including support for Semantic Telemetry Layers.
"""

import json
import logging as stdlib_logging
import os
import sys
from typing import TYPE_CHECKING, Any, TextIO, cast

from attrs import define, field
import structlog

from pyvider.telemetry.logger.custom_processors import (
    StructlogProcessor,
    add_log_level_custom,
    add_logger_name_emoji_prefix,
    filter_by_level_custom,
)
from pyvider.telemetry.types import (
    _VALID_FORMATTER_TUPLE,
    _VALID_LOG_LEVEL_TUPLE,
    TRACE_LEVEL_NUM,
    ConsoleFormatterStr,
    CustomDasEmojiSet,
    LogLevelStr,
    SemanticFieldDefinition,
    SemanticLayer,
)

if TYPE_CHECKING:
    from pyvider.telemetry.core import ResolvedSemanticConfig

_LEVEL_TO_NUMERIC: dict[LogLevelStr, int] = {
    "CRITICAL": stdlib_logging.CRITICAL,
    "ERROR": stdlib_logging.ERROR,
    "WARNING": stdlib_logging.WARNING,
    "INFO": stdlib_logging.INFO,
    "DEBUG": stdlib_logging.DEBUG,
    "TRACE": TRACE_LEVEL_NUM,
    "NOTSET": stdlib_logging.NOTSET,
}

DEFAULT_ENV_CONFIG: dict[str, str] = {
    "PYVIDER_LOG_LEVEL": "DEBUG",
    "PYVIDER_LOG_CONSOLE_FORMATTER": "key_value",
    "PYVIDER_LOG_OMIT_TIMESTAMP": "false",
    "PYVIDER_TELEMETRY_DISABLED": "false",
    "PYVIDER_LOG_MODULE_LEVELS": "",
    "PYVIDER_LOG_ENABLED_SEMANTIC_LAYERS": "",
}

config_warnings_logger = stdlib_logging.getLogger("pyvider.telemetry.config_warnings")
_config_warning_formatter = stdlib_logging.Formatter(
    "[Pyvider Config Warning] %(levelname)s (%(name)s): %(message)s"
)

def _ensure_config_logger_handler(logger: stdlib_logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    stderr_handler = stdlib_logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(_config_warning_formatter)
    logger.addHandler(stderr_handler)
    logger.setLevel(stdlib_logging.WARNING)
    logger.propagate = False


@define(frozen=True, slots=True)
class LoggingConfig:
    """Configuration specific to logging behavior within Pyvider Telemetry."""
    default_level: LogLevelStr = field(default="DEBUG")
    module_levels: dict[str, LogLevelStr] = field(factory=dict)
    console_formatter: ConsoleFormatterStr = field(default="key_value")
    logger_name_emoji_prefix_enabled: bool = field(default=True)
    das_emoji_prefix_enabled: bool = field(default=True)
    omit_timestamp: bool = field(default=False)
    enabled_semantic_layers: list[str] = field(factory=list)
    custom_semantic_layers: list[SemanticLayer] = field(factory=list)
    user_defined_emoji_sets: list[CustomDasEmojiSet] = field(factory=list)


@define(frozen=True, slots=True)
class TelemetryConfig:
    """Main configuration object for the Pyvider Telemetry system."""
    service_name: str | None = field(default=None)
    logging: LoggingConfig = field(factory=LoggingConfig)
    globally_disabled: bool = field(default=False)

    @classmethod
    def from_env(cls) -> "TelemetryConfig":
        """Creates a `TelemetryConfig` instance by parsing relevant environment variables."""
        _apply_default_env_config()

        service_name_env: str | None = os.getenv(
            "OTEL_SERVICE_NAME", os.getenv("PYVIDER_SERVICE_NAME")
        )

        raw_default_log_level: str = os.getenv("PYVIDER_LOG_LEVEL", "DEBUG").upper()
        default_log_level: LogLevelStr
        if raw_default_log_level in _VALID_LOG_LEVEL_TUPLE:
            default_log_level = cast(LogLevelStr, raw_default_log_level)
        else:
            _ensure_config_logger_handler(config_warnings_logger)
            config_warnings_logger.warning(
                f"⚙️➡️⚠️ Invalid PYVIDER_LOG_LEVEL '{raw_default_log_level}'. Defaulting to DEBUG."
            )
            default_log_level = "DEBUG"

        raw_console_formatter: str = os.getenv(
            "PYVIDER_LOG_CONSOLE_FORMATTER", "key_value"
        ).lower()
        console_formatter: ConsoleFormatterStr
        if raw_console_formatter in _VALID_FORMATTER_TUPLE:
            console_formatter = cast(ConsoleFormatterStr, raw_console_formatter)
        else:
            _ensure_config_logger_handler(config_warnings_logger)
            config_warnings_logger.warning(
                f"⚙️➡️⚠️ Invalid PYVIDER_LOG_CONSOLE_FORMATTER '{raw_console_formatter}'. Defaulting to 'key_value'."
            )
            console_formatter = "key_value"

        logger_name_emoji_enabled: bool = _parse_bool_env_with_formatter_default(
            "PYVIDER_LOG_LOGGER_NAME_EMOJI_ENABLED", console_formatter
        )
        das_emoji_enabled: bool = _parse_bool_env_with_formatter_default(
            "PYVIDER_LOG_DAS_EMOJI_ENABLED", console_formatter
        )
        omit_timestamp: bool = _parse_bool_env("PYVIDER_LOG_OMIT_TIMESTAMP", False)
        globally_disabled: bool = _parse_bool_env("PYVIDER_TELEMETRY_DISABLED", False)

        module_levels = cls._parse_module_levels(os.getenv("PYVIDER_LOG_MODULE_LEVELS", ""))
        enabled_semantic_layers = [
            layer.strip() for layer in os.getenv("PYVIDER_LOG_ENABLED_SEMANTIC_LAYERS", "").split(",") if layer.strip()
        ]

        custom_semantic_layers = cls._parse_custom_layers_from_env()
        user_defined_emoji_sets = cls._parse_user_emoji_sets_from_env()

        log_cfg = LoggingConfig(
            default_level=default_log_level,
            module_levels=module_levels,
            console_formatter=console_formatter,
            logger_name_emoji_prefix_enabled=logger_name_emoji_enabled,
            das_emoji_prefix_enabled=das_emoji_enabled,
            omit_timestamp=omit_timestamp,
            enabled_semantic_layers=enabled_semantic_layers,
            custom_semantic_layers=custom_semantic_layers,
            user_defined_emoji_sets=user_defined_emoji_sets,
        )

        return cls(
            service_name=service_name_env, logging=log_cfg, globally_disabled=globally_disabled
        )

    @staticmethod
    def _parse_custom_layers_from_env() -> list[SemanticLayer]:
        custom_layers_json = os.getenv("PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS", "[]")
        custom_semantic_layers: list[SemanticLayer] = []
        try:
            parsed_custom_layers = json.loads(custom_layers_json)
            if not isinstance(parsed_custom_layers, list): return []
            for layer_data in parsed_custom_layers:
                try:
                    if not isinstance(layer_data, dict): continue
                    emoji_sets_data = layer_data.get("emoji_sets", [])
                    field_defs_data = layer_data.get("field_definitions", [])
                    custom_emoji_sets_for_layer = [CustomDasEmojiSet(**es_data) for es_data in emoji_sets_data if isinstance(es_data, dict)]
                    custom_field_defs_for_layer = [SemanticFieldDefinition(**fd_data) for fd_data in field_defs_data if isinstance(fd_data, dict)]
                    custom_semantic_layers.append(SemanticLayer(
                        name=layer_data.get("name", "unnamed_custom_layer"),
                        description=layer_data.get("description"),
                        emoji_sets=custom_emoji_sets_for_layer,
                        field_definitions=custom_field_defs_for_layer,
                        priority=layer_data.get("priority", 0)
                    ))
                except (TypeError, ValueError) as e:
                    _ensure_config_logger_handler(config_warnings_logger)
                    config_warnings_logger.warning(f"⚙️➡️⚠️ Error parsing data for a custom layer: {e}. Skipping item.")
        except json.JSONDecodeError:
            _ensure_config_logger_handler(config_warnings_logger)
            config_warnings_logger.warning("⚙️➡️⚠️ Invalid JSON in PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS. Using empty list.")
        return custom_semantic_layers

    @staticmethod
    def _parse_user_emoji_sets_from_env() -> list[CustomDasEmojiSet]:
        user_sets_json = os.getenv("PYVIDER_LOG_USER_DEFINED_EMOJI_SETS", "[]")
        user_defined_emoji_sets: list[CustomDasEmojiSet] = []
        try:
            parsed_user_sets = json.loads(user_sets_json)
            if not isinstance(parsed_user_sets, list): return []
            for set_data in parsed_user_sets:
                try:
                    if isinstance(set_data, dict):
                        user_defined_emoji_sets.append(CustomDasEmojiSet(**set_data))
                except (TypeError, ValueError) as e:
                    _ensure_config_logger_handler(config_warnings_logger)
                    config_warnings_logger.warning(f"⚙️➡️⚠️ Error parsing data for an emoji set: {e}. Skipping item.")
        except json.JSONDecodeError:
            _ensure_config_logger_handler(config_warnings_logger)
            config_warnings_logger.warning("⚙️➡️⚠️ Invalid JSON in PYVIDER_LOG_USER_DEFINED_EMOJI_SETS. Using empty list.")
        return user_defined_emoji_sets

    @staticmethod
    def _parse_module_levels(levels_str: str) -> dict[str, LogLevelStr]:
        levels: dict[str, LogLevelStr] = {}
        if not levels_str.strip(): return levels
        for item in levels_str.split(","):
            item = item.strip()
            if not item: continue
            parts = item.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                module_name, level_name_raw = parts[0].strip(), parts[1].strip().upper()
                if level_name_raw in _VALID_LOG_LEVEL_TUPLE:
                    levels[module_name] = cast(LogLevelStr, level_name_raw)
                else:
                    _ensure_config_logger_handler(config_warnings_logger)
                    config_warnings_logger.warning(f"⚙️➡️⚠️ Invalid log level '{level_name_raw}' for module '{module_name}'. Skipping.")
            else:
                _ensure_config_logger_handler(config_warnings_logger)
                config_warnings_logger.warning(f"⚙️➡️⚠️ Invalid item '{item}' in PYVIDER_LOG_MODULE_LEVELS. Skipping.")
        return levels

def _apply_default_env_config() -> None:
    for key, default_value in DEFAULT_ENV_CONFIG.items():
        os.environ.setdefault(key, default_value)

def _parse_bool_env(env_var: str, default: bool) -> bool:
    value = os.getenv(env_var)
    return value.lower() == "true" if value is not None else default

def _parse_bool_env_with_formatter_default(env_var: str, formatter: ConsoleFormatterStr) -> bool:
    value = os.getenv(env_var)
    return value.lower() == "true" if value is not None else (formatter == "key_value")

def _config_create_service_name_processor(service_name: str | None) -> StructlogProcessor:
    def processor(_logger: Any, _method_name: str, event_dict: structlog.types.EventDict) -> structlog.types.EventDict:
        if service_name is not None: event_dict["service_name"] = service_name
        return event_dict
    return cast(StructlogProcessor, processor)

def _config_create_timestamp_processors(omit_timestamp: bool) -> list[StructlogProcessor]:
    processors: list[StructlogProcessor] = [structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False)]
    if omit_timestamp:
        def pop_timestamp_processor(_logger: Any, _method_name: str, event_dict: structlog.types.EventDict) -> structlog.types.EventDict:
            event_dict.pop("timestamp", None)
            return event_dict
        processors.append(cast(StructlogProcessor, pop_timestamp_processor))
    return processors

def _config_create_emoji_processors(logging_config: LoggingConfig, resolved_semantic_config: "ResolvedSemanticConfig") -> list[StructlogProcessor]:
    processors: list[StructlogProcessor] = []
    if logging_config.logger_name_emoji_prefix_enabled:
        processors.append(cast(StructlogProcessor, add_logger_name_emoji_prefix))
    if logging_config.das_emoji_prefix_enabled:
        # FIX: Create the processor as a closure with the resolved config
        resolved_field_definitions, resolved_emoji_sets_lookup = resolved_semantic_config

        def add_das_emoji_prefix_closure(_logger: Any, _method_name: str, event_dict: structlog.types.EventDict) -> structlog.types.EventDict:
            # This inner function now has access to the resolved config from its closure scope
            from pyvider.telemetry.logger.emoji_matrix import (
                PRIMARY_EMOJI,
                SECONDARY_EMOJI,
                TERTIARY_EMOJI,
            )
            final_das_prefix_parts: list[str] = []

            if resolved_field_definitions: # New Layered Semantic System is active
                for field_def in resolved_field_definitions:
                    value_from_event = event_dict.get(field_def.log_key)
                    if value_from_event is not None and field_def.emoji_set_name:
                        event_dict.pop(field_def.log_key, None)
                        emoji_set = resolved_emoji_sets_lookup.get(field_def.emoji_set_name)
                        if emoji_set:
                            value_str_lower = str(value_from_event).lower()
                            specific_emoji = emoji_set.emojis.get(value_str_lower)
                            default_key = field_def.default_emoji_override_key or emoji_set.default_emoji_key
                            default_emoji = emoji_set.emojis.get(default_key, "❓")
                            chosen_emoji = specific_emoji if specific_emoji is not None else default_emoji
                            final_das_prefix_parts.append(f"[{chosen_emoji}]")
                        else:
                            final_das_prefix_parts.append("[❓]")
            else: # Fallback to Legacy DAS System
                domain = event_dict.pop("domain", None)
                action = event_dict.pop("action", None)
                status = event_dict.pop("status", None)
                if domain or action or status:
                    domain_emoji = PRIMARY_EMOJI.get(str(domain).lower(), PRIMARY_EMOJI["default"]) if domain else PRIMARY_EMOJI["default"]
                    action_emoji = SECONDARY_EMOJI.get(str(action).lower(), SECONDARY_EMOJI["default"]) if action else SECONDARY_EMOJI["default"]
                    status_emoji = TERTIARY_EMOJI.get(str(status).lower(), TERTIARY_EMOJI["default"]) if status else TERTIARY_EMOJI["default"]
                    final_das_prefix_parts.extend([f"[{domain_emoji}]", f"[{action_emoji}]", f"[{status_emoji}]"])

            if final_das_prefix_parts:
                final_das_prefix_str = "".join(final_das_prefix_parts)
                event_msg = event_dict.get("event")
                event_dict["event"] = f"{final_das_prefix_str} {event_msg}" if event_msg is not None else final_das_prefix_str
            return event_dict

        processors.append(cast(StructlogProcessor, add_das_emoji_prefix_closure))
    return processors

def _build_core_processors_list(config: TelemetryConfig, resolved_semantic_config: "ResolvedSemanticConfig") -> list[StructlogProcessor]:
    log_cfg = config.logging
    processors: list[StructlogProcessor] = [
        structlog.contextvars.merge_contextvars,
        cast(StructlogProcessor, add_log_level_custom),
        cast(StructlogProcessor, filter_by_level_custom(
            default_level_str=log_cfg.default_level,
            module_levels=log_cfg.module_levels,
            level_to_numeric_map=_LEVEL_TO_NUMERIC
        )),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]
    processors.extend(_config_create_timestamp_processors(log_cfg.omit_timestamp))
    if config.service_name is not None:
        processors.append(_config_create_service_name_processor(config.service_name))
    processors.extend(_config_create_emoji_processors(log_cfg, resolved_semantic_config))
    return processors

def _config_create_json_formatter_processors() -> list[StructlogProcessor]:
    return [structlog.processors.format_exc_info, structlog.processors.JSONRenderer(serializer=json.dumps, sort_keys=False)]

def _config_create_keyvalue_formatter_processors(output_stream: TextIO) -> list[StructlogProcessor]:
    def pop_logger_name_processor(_logger: object, _method_name: str, event_dict: structlog.types.EventDict) -> structlog.types.EventDict:
        event_dict.pop("logger_name", None)
        return event_dict
    is_tty = hasattr(output_stream, 'isatty') and output_stream.isatty()
    return [
        cast(StructlogProcessor, pop_logger_name_processor),
        structlog.dev.ConsoleRenderer(colors=is_tty, exception_formatter=structlog.dev.plain_traceback)
    ]

def _build_formatter_processors_list(logging_config: LoggingConfig, output_stream: TextIO) -> list[StructlogProcessor]:
    match logging_config.console_formatter:
        case "json": return _config_create_json_formatter_processors()
        case "key_value": return _config_create_keyvalue_formatter_processors(output_stream)
        case unknown_formatter:
            _ensure_config_logger_handler(config_warnings_logger)
            config_warnings_logger.warning(f"⚙️➡️⚠️ Unknown formatter '{unknown_formatter}'. Defaulting to 'key_value'.")
            return _config_create_keyvalue_formatter_processors(output_stream)
