#
# core.py
#
"""
Pyvider Telemetry Core Initialization and Configuration.
Handles setup, global state, processor chain assembly (including semantic layer resolution),
and shutdown for the telemetry system.
"""

import io
import logging as stdlib_logging
import os
import sys
import threading
from typing import Any, TextIO, cast

import structlog
from structlog.types import BindableLogger

from pyvider.telemetry.config import (
    LoggingConfig,
    TelemetryConfig,
    _build_core_processors_list,
    _build_formatter_processors_list,
)
from pyvider.telemetry.logger import base as logger_base_module
from pyvider.telemetry.semantic_layers import (
    BUILTIN_SEMANTIC_LAYERS,
    LEGACY_DAS_EMOJI_SETS,
)
from pyvider.telemetry.types import (
    CustomDasEmojiSet,
    SemanticFieldDefinition,
    SemanticLayer,
)

_PYVIDER_SETUP_LOCK = threading.Lock() # A non-reentrant lock is fine with the refactored logic.
_PYVIDER_LOG_STREAM: TextIO = sys.stderr
_CORE_SETUP_LOGGER_NAME = "pyvider.telemetry.core_setup"
_EXPLICIT_SETUP_DONE = False

def _get_safe_stderr() -> TextIO:
    return sys.stderr if hasattr(sys, 'stderr') and sys.stderr is not None else io.StringIO()

def _set_log_stream_for_testing(stream: TextIO | None) -> None:
    global _PYVIDER_LOG_STREAM
    _PYVIDER_LOG_STREAM = stream if stream is not None else sys.stderr

def _ensure_stderr_default() -> None:
    global _PYVIDER_LOG_STREAM
    if _PYVIDER_LOG_STREAM is sys.stdout:
        _PYVIDER_LOG_STREAM = sys.stderr

def _create_core_setup_logger(globally_disabled: bool = False) -> stdlib_logging.Logger:
    logger = stdlib_logging.getLogger(_CORE_SETUP_LOGGER_NAME)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            if isinstance(h, stdlib_logging.StreamHandler) and h.stream not in (sys.stdout, sys.stderr, _PYVIDER_LOG_STREAM):
                h.close()
        except Exception:
            pass
    handler: stdlib_logging.Handler = stdlib_logging.NullHandler() if globally_disabled else stdlib_logging.StreamHandler(sys.stderr)
    if not globally_disabled:
        handler.setFormatter(stdlib_logging.Formatter("[Pyvider Setup] %(levelname)s (%(name)s): %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(getattr(stdlib_logging, os.getenv("PYVIDER_CORE_SETUP_LOG_LEVEL", "INFO").upper(), stdlib_logging.INFO))
    logger.propagate = False
    return logger

_core_setup_logger = _create_core_setup_logger()

ResolvedSemanticConfig = tuple[list[SemanticFieldDefinition], dict[str, CustomDasEmojiSet]]

def _resolve_active_semantic_config(logging_config: LoggingConfig, builtin_layers_registry: dict[str, SemanticLayer]) -> ResolvedSemanticConfig:
    resolved_fields_dict: dict[str, SemanticFieldDefinition] = {}
    resolved_emoji_sets_dict: dict[str, CustomDasEmojiSet] = {s.name: s for s in LEGACY_DAS_EMOJI_SETS}

    layers_to_process: list[SemanticLayer] = [
        builtin_layers_registry[name] for name in logging_config.enabled_semantic_layers if name in builtin_layers_registry
    ]
    layers_to_process.extend(logging_config.custom_semantic_layers)
    layers_to_process.sort(key=lambda layer: layer.priority)

    ordered_log_keys: list[str] = []
    seen_log_keys: set[str] = set()

    for layer in layers_to_process:
        for emoji_set in layer.emoji_sets:
            resolved_emoji_sets_dict[emoji_set.name] = emoji_set
        for field_def in layer.field_definitions:
            resolved_fields_dict[field_def.log_key] = field_def
            if field_def.log_key not in seen_log_keys:
                ordered_log_keys.append(field_def.log_key)
                seen_log_keys.add(field_def.log_key)

    for user_emoji_set in logging_config.user_defined_emoji_sets:
        resolved_emoji_sets_dict[user_emoji_set.name] = user_emoji_set

    final_ordered_field_definitions = [resolved_fields_dict[log_key] for log_key in ordered_log_keys]
    return final_ordered_field_definitions, resolved_emoji_sets_dict

def _build_complete_processor_chain(config: TelemetryConfig, resolved_semantic_config: ResolvedSemanticConfig) -> list[Any]:
    core_processors = _build_core_processors_list(config, resolved_semantic_config)
    formatter_processors = _build_formatter_processors_list(config.logging, _PYVIDER_LOG_STREAM)
    _core_setup_logger.info(f"📝➡️🎨 Configured {config.logging.console_formatter} renderer.")
    return cast(list[Any], core_processors + formatter_processors)

def _apply_structlog_configuration(processors: list[Any]) -> None:
    stream_name = 'sys.stderr' if sys.stderr == _PYVIDER_LOG_STREAM else 'custom stream (testing)'
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(file=_PYVIDER_LOG_STREAM),
        wrapper_class=cast(type[BindableLogger], structlog.BoundLogger),
        cache_logger_on_first_use=True,
    )
    _core_setup_logger.info(f"📝➡️✅ structlog configured. Wrapper: BoundLogger. Output: {stream_name}.")

def _configure_structlog_output(config: TelemetryConfig, resolved_semantic_config: ResolvedSemanticConfig) -> None:
    processors = _build_complete_processor_chain(config, resolved_semantic_config)
    _apply_structlog_configuration(processors)

def _handle_globally_disabled_setup() -> None:
    _core_setup_logger.info("⚙️➡️🚫 Pyvider telemetry globally disabled.")
    structlog.configure(processors=[], logger_factory=structlog.ReturnLoggerFactory(), cache_logger_on_first_use=True)

def reset_pyvider_setup_for_testing() -> None:
    """
    Resets `structlog` defaults and Pyvider Telemetry's internal logger state.
    This is a test utility and should not be called by production code.
    """
    global _PYVIDER_LOG_STREAM, _core_setup_logger, _EXPLICIT_SETUP_DONE
    with _PYVIDER_SETUP_LOCK:
        structlog.reset_defaults()
        logger_base_module.logger._is_configured_by_setup = False
        logger_base_module.logger._active_config = None
        logger_base_module.logger._active_resolved_semantic_config = None
        logger_base_module._LAZY_SETUP_STATE.update({"done": False, "error": None, "in_progress": False})
        _PYVIDER_LOG_STREAM = sys.stderr
        _EXPLICIT_SETUP_DONE = False
        _core_setup_logger = _create_core_setup_logger()

def _internal_setup(config: TelemetryConfig | None = None, is_explicit_call: bool = False) -> None:
    """
    The single, internal setup function that both explicit and lazy setup call.
    It is protected by the _PYVIDER_SETUP_LOCK in its callers.
    """
    global _core_setup_logger

    # This function assumes the lock is already held.
    # 1. Reset all relevant state.
    structlog.reset_defaults()
    logger_base_module.logger._is_configured_by_setup = False
    logger_base_module.logger._active_config = None
    logger_base_module.logger._active_resolved_semantic_config = None
    logger_base_module._LAZY_SETUP_STATE.update({"done": False, "error": None, "in_progress": False})

    # 2. Determine configuration
    current_config = config if config is not None else TelemetryConfig.from_env()
    _core_setup_logger = _create_core_setup_logger(globally_disabled=current_config.globally_disabled)

    if not current_config.globally_disabled:
        _core_setup_logger.info("⚙️➡️🚀 Starting Pyvider (structlog) setup...")

    # 3. Resolve semantic config
    resolved_semantic_config = _resolve_active_semantic_config(current_config.logging, BUILTIN_SEMANTIC_LAYERS)

    # 4. Apply configuration
    if current_config.globally_disabled:
        _handle_globally_disabled_setup()
    else:
        _configure_structlog_output(current_config, resolved_semantic_config)

    # 5. Update state flags
    logger_base_module.logger._is_configured_by_setup = is_explicit_call
    logger_base_module.logger._active_config = current_config
    logger_base_module.logger._active_resolved_semantic_config = resolved_semantic_config
    logger_base_module._LAZY_SETUP_STATE["done"] = True

    if not current_config.globally_disabled:
        _core_setup_logger.info("⚙️➡️✅ Pyvider (structlog) setup completed.")

def setup_telemetry(config: TelemetryConfig | None = None) -> None:
    """
    Initializes or reconfigures the Pyvider Telemetry system.
    """
    global _EXPLICIT_SETUP_DONE
    with _PYVIDER_SETUP_LOCK:
        _ensure_stderr_default()
        _internal_setup(config, is_explicit_call=True)
        _EXPLICIT_SETUP_DONE = True

async def shutdown_pyvider_telemetry(timeout_millis: int = 5000) -> None:
    _core_setup_logger.info("🔌➡️🏁 Pyvider telemetry shutdown called.")
