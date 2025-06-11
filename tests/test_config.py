#
# tests/test_config.py
#
"""
Unit tests for processor assembly helper functions in pyvider.telemetry.config.
"""
import io
import json
from typing import Any

from pytest import CaptureFixture
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer, TimeStamper

from pyvider.telemetry.config import (
    LoggingConfig,
    TelemetryConfig,
    _build_core_processors_list,
    _build_formatter_processors_list,
    _config_create_emoji_processors,
    _config_create_timestamp_processors,
    _ensure_config_logger_handler,
    config_warnings_logger,
)
from pyvider.telemetry.core import (
    _resolve_active_semantic_config,
)
from pyvider.telemetry.semantic_layers import BUILTIN_SEMANTIC_LAYERS


def get_proc_name(proc: Any) -> str:
    if hasattr(proc, '__name__'):
        return proc.__name__
    if isinstance(proc, TimeStamper):
        return "TimeStamper"
    if isinstance(proc, JSONRenderer):
        return "JSONRenderer"
    if isinstance(proc, ConsoleRenderer):
        return "ConsoleRenderer"
    return proc.__class__.__name__ if hasattr(proc, '__class__') else str(type(proc))

class TestConfigTimestampProcessors:
    def test_timestamp_processors_default(self) -> None:
        processors = _config_create_timestamp_processors(omit_timestamp=False)
        assert len(processors) == 1 and get_proc_name(processors[0]) == "TimeStamper"

    def test_timestamp_processors_omitted(self) -> None:
        processors = _config_create_timestamp_processors(omit_timestamp=True)
        assert len(processors) == 2 and get_proc_name(processors[1]) == "pop_timestamp_processor"

class TestConfigEmojiProcessors:
    def test_all_emojis_enabled(self) -> None:
        config = LoggingConfig(logger_name_emoji_prefix_enabled=True, das_emoji_prefix_enabled=True)
        resolved_config = _resolve_active_semantic_config(config, BUILTIN_SEMANTIC_LAYERS)
        processors = _config_create_emoji_processors(config, resolved_config)
        assert len(processors) == 2 and get_proc_name(processors[0]) == "add_logger_name_emoji_prefix" and callable(processors[1])

class TestBuildFormatterProcessorsList:
    def test_build_json_formatter(self) -> None:
        processors = _build_formatter_processors_list(LoggingConfig(console_formatter="json"), io.StringIO())
        assert [get_proc_name(p) for p in processors] == ["ExceptionRenderer", "JSONRenderer"]

    def test_build_keyvalue_formatter(self) -> None:
        processors = _build_formatter_processors_list(LoggingConfig(console_formatter="key_value"), io.StringIO())
        assert [get_proc_name(p) for p in processors] == ["pop_logger_name_processor", "ConsoleRenderer"]

class TestBuildCoreProcessorsList:
    def test_default_config(self) -> None:
        config = TelemetryConfig()
        resolved_semantic_config = _resolve_active_semantic_config(config.logging, BUILTIN_SEMANTIC_LAYERS)
        processors = _build_core_processors_list(config, resolved_semantic_config)
        assert len(processors) == 8 and get_proc_name(processors[6]) == "add_logger_name_emoji_prefix"




class TestTelemetryConfigFromEnvSemanticLayers:
    def test_from_env_parses_enabled_semantic_layers(self, monkeypatch) -> None:
        monkeypatch.setenv("PYVIDER_LOG_ENABLED_SEMANTIC_LAYERS", "llm, http , database ")
        config = TelemetryConfig.from_env()
        assert config.logging.enabled_semantic_layers == ["llm", "http", "database"]

    def test_from_env_handles_malformed_custom_layers_json(self, monkeypatch, capsys: CaptureFixture) -> None:
        monkeypatch.setenv("PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS", "[{'name': 'badjson']")
        _ensure_config_logger_handler(config_warnings_logger)
        config = TelemetryConfig.from_env()
        assert config.logging.custom_semantic_layers == []
        assert "Invalid JSON in PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS" in capsys.readouterr().err

    def test_from_env_handles_type_error_in_custom_layer_data(self, monkeypatch, capsys: CaptureFixture) -> None:
        custom_layers_json = json.dumps([{"name": "my_layer", "priority": "not_an_int"}])
        monkeypatch.setenv("PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS", custom_layers_json)
        _ensure_config_logger_handler(config_warnings_logger)
        config = TelemetryConfig.from_env()
        assert config.logging.custom_semantic_layers == []
        assert "Error parsing data for a custom layer" in capsys.readouterr().err
