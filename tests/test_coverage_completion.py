#
# test_coverage_completion.py
#
"""
Additional tests specifically designed to achieve 100% code coverage.
"""
import asyncio
from collections.abc import Callable
import io
import logging as stdlib_logging
import os
import sys
import threading
from unittest.mock import patch

import pytest
import structlog

from pyvider.telemetry import (
    LoggingConfig,
    TelemetryConfig,
    logger,
    setup_telemetry,
    shutdown_pyvider_telemetry,
)
from pyvider.telemetry.core import (
    _create_core_setup_logger,
    _handle_globally_disabled_setup,
    _set_log_stream_for_testing,
    reset_pyvider_setup_for_testing,
)
from pyvider.telemetry.logger.custom_processors import (
    _compute_emoji_for_logger_name,
    clear_emoji_cache,
    get_emoji_cache_stats,
)
from pyvider.telemetry.logger.emoji_matrix import show_emoji_matrix
from pyvider.telemetry.types import (
    LogLevelStr,
)


def test_core_setup_logger_with_existing_handlers() -> None:
    test_logger_name = "test.cleanup.logger"
    test_logger = stdlib_logging.getLogger(test_logger_name)
    test_logger.addHandler(stdlib_logging.StreamHandler())
    test_logger.addHandler(stdlib_logging.StreamHandler())
    with patch('pyvider.telemetry.core._CORE_SETUP_LOGGER_NAME', test_logger_name):
        result_logger = _create_core_setup_logger(globally_disabled=False)
    assert result_logger.hasHandlers() and len(result_logger.handlers) == 1

def test_globally_disabled_setup_with_existing_logger() -> None:
    temp_logger_name = "pyvider.telemetry.core_setup_temp_disabled_msg"
    temp_logger = stdlib_logging.getLogger(temp_logger_name)
    temp_logger.addHandler(stdlib_logging.StreamHandler(sys.stderr))
    _handle_globally_disabled_setup()
    assert temp_logger.hasHandlers()

def test_logger_base_format_message_edge_cases() -> None:
    setup_telemetry()
    assert logger._format_message_with_args("test message", ()) == "test message"
    assert logger._format_message_with_args("test %s", ("value",)) == "test value"
    assert logger._format_message_with_args("test %q invalid", ("value",)) == "test %q invalid value"
    assert logger._format_message_with_args("test %s %s", ("only_one",)) == "test %s %s only_one"
    assert logger._format_message_with_args("test %s %d", ("str", 42)) == "test str 42"

def test_logger_base_setattr_coverage() -> None:
    setup_telemetry()
    logger._internal_logger = "test"
    logger.test_attr = "test_value"
    assert logger.test_attr == "test_value"

def test_custom_processors_emoji_cache_functions() -> None:
    clear_emoji_cache()
    stats = get_emoji_cache_stats()
    assert stats["cache_size"] == 0
    setup_telemetry(TelemetryConfig(logging=LoggingConfig(logger_name_emoji_prefix_enabled=True)))
    logger.get_logger("pyvider.telemetry.core.test").info("Test message 1")
    logger.get_logger("unknown.test").info("Test message 2")
    assert get_emoji_cache_stats()["cache_size"] > 0
    clear_emoji_cache()
    assert get_emoji_cache_stats()["cache_size"] == 0

def test_emoji_matrix_display(
    setup_pyvider_telemetry_for_test: Callable[[TelemetryConfig | None], None],
    captured_stderr_for_pyvider: io.StringIO,
) -> None:
    # Test that it does nothing by default
    show_emoji_matrix()
    assert captured_stderr_for_pyvider.getvalue() == ""

    # Test that it prints when env var is set
    with patch.dict(os.environ, {"PYVIDER_SHOW_EMOJI_MATRIX": "true"}):
        # Use a simple config for the test
        setup_pyvider_telemetry_for_test(TelemetryConfig())
        show_emoji_matrix()
        output = captured_stderr_for_pyvider.getvalue()
        # FIX: Assert the correct output string for legacy mode
        assert "Pyvider Telemetry: Legacy DAS Emoji Contract" in output
        assert "Primary Emojis" in output

def test_trace_level_custom_logger_name() -> None:
    setup_telemetry(TelemetryConfig(logging=LoggingConfig(default_level="TRACE")))
    logger.trace("Custom trace message", _pyvider_logger_name="custom.trace.test")
    logger.trace("Trace with %s and %d", "args", 42, _pyvider_logger_name="custom.trace.args")

def test_core_setup_environment_variable_edge_cases() -> None:
    with patch.dict(os.environ, {"PYVIDER_CORE_SETUP_LOG_LEVEL": "INVALID"}):
        assert _create_core_setup_logger().level == 20

def test_shutdown_telemetry_coverage() -> None:
    setup_telemetry()
    asyncio.run(shutdown_pyvider_telemetry(timeout_millis=1000))

def test_level_filter_edge_cases() -> None:
    from pyvider.telemetry.logger.custom_processors import _LevelFilter
    level_map: dict[LogLevelStr, int] = {"CRITICAL": 50, "ERROR": 40, "WARNING": 30, "INFO": 20, "DEBUG": 10, "TRACE": 5, "NOTSET": 0}
    filter_instance = _LevelFilter("INFO", {"app": "DEBUG"}, level_map)
    with pytest.raises(structlog.DropEvent):
        filter_instance(None, None, {"logger_name": "unnamed", "level": "debug"})
    assert filter_instance(None, None, {"logger_name": "test", "level": "UNKNOWN"})

def test_emoji_computation_edge_cases() -> None:
    assert _compute_emoji_for_logger_name("default.something") == "🔹"
    assert _compute_emoji_for_logger_name("default") == "🔹"
    assert _compute_emoji_for_logger_name("completely.unknown") == "🔹"

def test_concurrent_setup_and_reset() -> None:
    def setup_worker() -> None:
        setup_telemetry(TelemetryConfig(service_name="concurrent_test"))
    def reset_worker() -> None:
        reset_pyvider_setup_for_testing()
    threads = [threading.Thread(target=setup_worker if i % 2 == 0 else reset_worker) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

def test_stream_testing_functions() -> None:
    test_stream = io.StringIO()
    _set_log_stream_for_testing(test_stream)
    _set_log_stream_for_testing(None)

def test_processor_chain_edge_cases() -> None:
    setup_telemetry(TelemetryConfig(logging=LoggingConfig(logger_name_emoji_prefix_enabled=False, das_emoji_prefix_enabled=False, omit_timestamp=True)))
    logger.info("Test message")

def test_complex_nested_logger_names() -> None:
    setup_telemetry()
    logger.get_logger("pyvider.telemetry.core.sub.module.deep.nest").info("Deep nested message")
    logger.get_logger("app.module-1.sub_module.v2").info("Special character message")

def test_exception_logging_edge_cases() -> None:
    setup_telemetry()
    try:
        raise ValueError("Test")
    except ValueError:
        logger.exception("Error %d", 5, operation="test")
    try:
        raise ConnectionError("Connection failed")
    except ConnectionError:
        logger.exception("Connection error", domain="network", action="connect", status="error")

@pytest.mark.asyncio
async def test_async_logging_edge_cases() -> None:
    setup_telemetry()
    async def task() -> None:
        try:
            raise RuntimeError("Async task failed")
        except RuntimeError:
            logger.exception("Async task exception", task_id="async_001")
    await task()

def test_warning_alias() -> None:
    setup_telemetry()
    assert logger.warn == logger.warning
    logger.warn("Warning message using alias", code="W001")
