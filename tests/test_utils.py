# tests/test_utils.py
"""
Tests for utility functions in pyvider.telemetry.utils.
"""
from collections.abc import Callable
import io
import re

import pytest

from pyvider.telemetry import (
    LoggingConfig,
    TelemetryConfig,
    logger as global_logger,
)
from pyvider.telemetry.utils import _PYVIDER_CONTEXT_TRACE_ID, timed_block


def parse_kv_log_line(line: str) -> dict:
    """A robust parser for key=value log lines that handles emojis and spaces in messages."""
    # Remove timestamp
    line = re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}\s+", "", line)

    # Extract level
    level_match = re.search(r"\[\s*([a-zA-Z]+)\s*\]", line)
    level = level_match.group(1).lower() if level_match else ""
    content_after_level = line[level_match.end():].strip() if level_match else line

    data = {"level": level}

    # FIX: Regex now handles single/double quoted strings and unquoted values
    kv_pairs = re.findall(r'([\w.]+)=(".*?"|\'.*?\'|\S+)', content_after_level)

    # Find the start of the key-value section to isolate the event message
    first_kv_match = re.search(r'[\w.]+=(".*?"|\'.*?\'|\S+)', content_after_level)

    event_part = content_after_level[:first_kv_match.start()] if first_kv_match else content_after_level

    data["event"] = event_part.strip()

    for key, value in kv_pairs:
        # Strip matching quotes if they exist
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        if value.isdigit():
            data[key] = int(value)
        elif value.lower() == "true":
            data[key] = True
        elif value.lower() == "false":
            data[key] = False
        else:
            try:
                data[key] = float(value)
            except ValueError:
                data[key] = value
    return data

@pytest.fixture
def setup_telemetry_for_utils(
    setup_pyvider_telemetry_for_test: Callable[[TelemetryConfig | None], None]
) -> None:
    """Fixture to set up telemetry for util tests with logger name emojis disabled."""
    config = TelemetryConfig(
        logging=LoggingConfig(
            default_level="INFO",
            console_formatter="key_value",
            logger_name_emoji_prefix_enabled=False,
        )
    )
    setup_pyvider_telemetry_for_test(config)

@pytest.mark.usefixtures("setup_telemetry_for_utils")
class TestTimedBlock:
    def test_successful_execution(self, captured_stderr_for_pyvider: io.StringIO) -> None:
        with timed_block(global_logger, "my_successful_op", layer_keys={"component": "test_util"}, project_id=123):
            pass
        captured = captured_stderr_for_pyvider.getvalue()
        log_lines = [line for line in captured.strip().splitlines() if "my_successful_op" in line]
        assert len(log_lines) == 1
        log_data = parse_kv_log_line(log_lines[0])
        assert log_data.get("event", "").strip() == "my_successful_op"
        assert log_data.get("project_id") == 123
        assert log_data.get("component") == "test_util"
        assert log_data.get("outcome") == "success"
        assert "duration_ms" in log_data

    def test_execution_with_exception(self, captured_stderr_for_pyvider: io.StringIO) -> None:
        with pytest.raises(ValueError, match="Simulated error"):
            with timed_block(global_logger, "my_failing_op", user_id="user_abc"):
                raise ValueError("Simulated error")
        captured = captured_stderr_for_pyvider.getvalue()
        log_lines = [line for line in captured.strip().splitlines() if "my_failing_op" in line]
        assert len(log_lines) == 1
        log_data = parse_kv_log_line(log_lines[0])
        assert log_data.get("event", "").endswith("my_failing_op")
        assert log_data.get("user_id") == "user_abc"
        assert log_data.get("outcome") == "error"
        assert log_data.get("error.message") == "Simulated error"

    def test_log_level_for_outcome(self, captured_stderr_for_pyvider: io.StringIO) -> None:
        with timed_block(global_logger, "success_op_info_level"):
            pass
        assert "[info " in captured_stderr_for_pyvider.getvalue().lower()

        # Clear buffer for next check
        captured_stderr_for_pyvider.seek(0)
        captured_stderr_for_pyvider.truncate(0)

        with pytest.raises(RuntimeError):
            with timed_block(global_logger, "error_op_error_level"):
                raise RuntimeError("err")
        assert "[error " in captured_stderr_for_pyvider.getvalue().lower()

    def test_trace_id_from_contextvar(self, captured_stderr_for_pyvider: io.StringIO) -> None:
        token = _PYVIDER_CONTEXT_TRACE_ID.set("test-trace-12345")
        try:
            with timed_block(global_logger, "op_with_trace_id"):
                pass
        finally:
            _PYVIDER_CONTEXT_TRACE_ID.reset(token)
        captured = captured_stderr_for_pyvider.getvalue()
        log_lines = [line for line in captured.strip().splitlines() if "op_with_trace_id" in line]
        assert len(log_lines) == 1
        assert parse_kv_log_line(log_lines[0]).get("trace_id") == "test-trace-12345"

    def test_trace_id_from_initial_kvs_overrides_contextvar(self, captured_stderr_for_pyvider: io.StringIO) -> None:
        token = _PYVIDER_CONTEXT_TRACE_ID.set("context-id")
        try:
            with timed_block(global_logger, "op_override_trace_id", trace_id="kvs-id"):
                pass
        finally:
            _PYVIDER_CONTEXT_TRACE_ID.reset(token)
        captured = captured_stderr_for_pyvider.getvalue()
        log_lines = [line for line in captured.strip().splitlines() if "op_override_trace_id" in line]
        assert len(log_lines) == 1
        assert parse_kv_log_line(log_lines[0]).get("trace_id") == "kvs-id"
