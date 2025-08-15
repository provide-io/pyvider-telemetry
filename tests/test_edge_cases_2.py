#
# tests/test_more_coverage.py
#
"""
Tests specifically designed to increase code coverage by targeting edge cases
and error-handling paths identified in coverage reports.
"""
from collections.abc import Callable
import io
import json
import logging as stdlib_logging
import os
from unittest.mock import MagicMock, patch

import pytest
import structlog

from pyvider.telemetry import (
    LoggingConfig,
    SemanticLayer,
    TelemetryConfig,
    logger,
)
from pyvider.telemetry.config import _build_formatter_processors_list
from pyvider.telemetry.core import (
    _CORE_SETUP_LOGGER_NAME,
    _create_core_setup_logger,
)
from pyvider.telemetry.logger import base as pyvider_logger_base
from pyvider.telemetry.logger.custom_processors import (
    add_log_level_custom,
)
from pyvider.telemetry.logger.emoji_matrix import show_emoji_matrix

# --- Tests for src/pyvider/telemetry/config.py ---

def test_config_from_env_malformed_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Covers error handling for invalid JSON in environment variables."""
    # Test malformed custom layers JSON
    monkeypatch.setenv("PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS", "[{'name': 'badjson'}]")
    config = TelemetryConfig.from_env()
    assert config.logging.custom_semantic_layers == []
    assert "Invalid JSON in PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS" in capsys.readouterr().err

    # Test malformed user emoji sets JSON
    monkeypatch.setenv("PYVIDER_LOG_USER_DEFINED_EMOJI_SETS", "[{'name': 'badjson'}]")
    config = TelemetryConfig.from_env()
    assert config.logging.user_defined_emoji_sets == []
    assert "Invalid JSON in PYVIDER_LOG_USER_DEFINED_EMOJI_SETS" in capsys.readouterr().err


def test_config_from_env_type_error_in_data(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Covers TypeError handling for malformed data within valid JSON."""
    # Test TypeError in custom layers (e.g., priority is not an int)
    custom_layers_json = json.dumps([{"name": "my_layer", "priority": "not-an-int"}])
    monkeypatch.setenv("PYVIDER_LOG_CUSTOM_SEMANTIC_LAYERS", custom_layers_json)
    config = TelemetryConfig.from_env()
    assert config.logging.custom_semantic_layers == []
    assert "Error parsing data for a custom layer" in capsys.readouterr().err

    # Test TypeError in user emoji sets (e.g., emojis is not a dict)
    user_sets_json = json.dumps([{"name": "my_set", "emojis": ["not-a-dict"]}])
    monkeypatch.setenv("PYVIDER_LOG_USER_DEFINED_EMOJI_SETS", user_sets_json)
    config = TelemetryConfig.from_env()
    assert config.logging.user_defined_emoji_sets == []
    assert "Error parsing data for an emoji set" in capsys.readouterr().err


def test_config_unknown_formatter(capsys: pytest.CaptureFixture) -> None:
    """Covers the fallback mechanism for an unknown console formatter."""
    # This will trigger the warning and default to key_value
    config = LoggingConfig(console_formatter="invalid_formatter")  # type: ignore
    processors = _build_formatter_processors_list(config, io.StringIO())
    assert "Unknown formatter 'invalid_formatter'" in capsys.readouterr().err
    # Check that it defaulted to ConsoleRenderer, which is part of the key_value chain
    assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)


def test_config_dangling_emoji_set_reference(
    setup_pyvider_telemetry_for_test: Callable,
    captured_stderr_for_pyvider: io.StringIO,
) -> None:
    """Covers a semantic field referencing a non-existent emoji set."""
    from pyvider.telemetry.types import SemanticFieldDefinition

    dangling_field = SemanticFieldDefinition(
        log_key="dangling_key", emoji_set_name="non_existent_set"
    )
    layer = SemanticLayer(
        name="dangling_layer", field_definitions=[dangling_field]
    )
    config = TelemetryConfig(
        logging=LoggingConfig(
            enabled_semantic_layers=["dangling_layer"],
            custom_semantic_layers=[layer],
            das_emoji_prefix_enabled=True,
            logger_name_emoji_prefix_enabled=False,
        )
    )
    setup_pyvider_telemetry_for_test(config)

    logger.info("Testing dangling reference", dangling_key="some_value")
    output = captured_stderr_for_pyvider.getvalue()
    # Should fall back to the default question mark emoji
    assert "[❓] Testing dangling reference" in output


# --- Tests for src/pyvider/telemetry/core.py ---

def test_core_create_logger_handler_close_fails() -> None:
    """Covers the exception handling when a handler's close() method fails."""
    logger = stdlib_logging.getLogger(_CORE_SETUP_LOGGER_NAME)
    mock_handler = MagicMock(spec=stdlib_logging.StreamHandler)
    mock_handler.stream = io.StringIO()
    mock_handler.close.side_effect = RuntimeError("Cannot close")
    logger.addHandler(mock_handler)

    # Should not raise an exception
    _create_core_setup_logger()


# --- Tests for src/pyvider/telemetry/logger/base.py ---

def test_base_get_config_exception() -> None:
    """Covers the case where structlog.get_config() raises an exception."""
    with patch("structlog.get_config", side_effect=Exception("get_config failed")):
        # The call should be handled gracefully and not crash
        logger._ensure_configured()
        assert True  # Test passes if it doesn't raise an unhandled exception


def test_base_emergency_fallback_fails() -> None:
    """Covers the fallback-of-the-fallback scenario."""
    with patch(
        "structlog.configure", side_effect=[Exception("Primary fallback fails"), None]
    ) as mock_configure:
        logger._setup_emergency_fallback()
        # Should call configure twice: once for the primary fallback (fails),
        # and once for the secondary fallback (succeeds).
        assert mock_configure.call_count == 2


# --- Tests for src/pyvider/telemetry/logger/custom_processors.py ---

def test_custom_processors_level_hint() -> None:
    """Covers the _pyvider_level_hint logic in add_log_level_custom."""
    event = add_log_level_custom(None, "info", {"_pyvider_level_hint": "CRITICAL"})
    assert event["level"] == "critical"


def test_custom_processors_method_name_matching() -> None:
    """Covers the match cases for method names in add_log_level_custom."""
    event_exc = add_log_level_custom(None, "exception", {})
    assert event_exc["level"] == "error"

    event_warn = add_log_level_custom(None, "warn", {})
    assert event_warn["level"] == "warning"

    event_msg = add_log_level_custom(None, "msg", {})
    assert event_msg["level"] == "info"


def test_custom_processors_full_emoji_cache(
    setup_pyvider_telemetry_for_test: Callable,
) -> None:
    """Covers the path where the emoji cache is full."""
    setup_pyvider_telemetry_for_test(
        TelemetryConfig(logging=LoggingConfig(logger_name_emoji_prefix_enabled=True))
    )
    with patch(
        "pyvider.telemetry.logger.custom_processors._EMOJI_CACHE_SIZE_LIMIT", 0
    ):
        # With cache size 0, this call will exercise the "cache is full" path
        logger.get_logger("some.new.logger").info("test")
        # Just needs to not crash
        assert True


# --- Tests for src/pyvider/telemetry/logger/emoji_matrix.py ---

def test_emoji_matrix_display_with_semantic_layers(
    setup_pyvider_telemetry_for_test: Callable,
    captured_stderr_for_pyvider: io.StringIO,
) -> None:
    """Covers displaying the matrix when semantic layers are active."""
    with patch.dict(os.environ, {"PYVIDER_SHOW_EMOJI_MATRIX": "true"}):
        config = TelemetryConfig(
            logging=LoggingConfig(enabled_semantic_layers=["http"])
        )
        setup_pyvider_telemetry_for_test(config)
        show_emoji_matrix()
        output = captured_stderr_for_pyvider.getvalue()
        assert "Active Semantic Layer Emoji Contract" in output
        assert "Log Key: 'http.method'" in output


def test_emoji_matrix_display_unresolved(capsys: pytest.CaptureFixture) -> None:
    """Covers displaying the matrix when config is not yet resolved."""
    with patch.dict(os.environ, {"PYVIDER_SHOW_EMOJI_MATRIX": "true"}):
        # Prevent lazy-init from running
        with patch.object(pyvider_logger_base.logger, "_ensure_configured"):
            # Ensure the attribute that is checked is None
            pyvider_logger_base.logger._active_resolved_semantic_config = None

            # Mock the logger that show_emoji_matrix will create
            mock_info_method = MagicMock()
            mock_created_logger = MagicMock()
            mock_created_logger.info = mock_info_method

            with patch.object(
                pyvider_logger_base.logger, "get_logger", return_value=mock_created_logger
            ):
                show_emoji_matrix()

                # Assert that the correct "unresolved" message was logged
                mock_info_method.assert_called_once()
                call_args, _ = mock_info_method.call_args
                output_message = call_args[0]
                assert "configuration not yet resolved" in output_message
