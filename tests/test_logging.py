#
# test_logging.py
#
"""
Tests for the Pyvider Telemetry logging system.
"""
import io
import json
import re
from typing import Any

import pytest
from pytest import CaptureFixture, MonkeyPatch

from pyvider.telemetry import (
    LoggingConfig,
    TelemetryConfig,
    logger as global_logger,
)


def _filter_application_logs(output: str) -> list[str]:
    return [line for line in output.strip().splitlines() if not line.startswith("[Pyvider Setup]") and line.strip()]

def assert_log_output(output: str, expected_level: str, expected_message_core: str, expected_kvs: dict[str, Any] | None = None, is_json: bool = False, expect_traceback_containing: str | None = None, expect_timestamp: bool = True) -> None:
    actual_log_lines = _filter_application_logs(output)
    is_expecting_empty = not expected_level and not expected_message_core and not expected_kvs and not expect_traceback_containing
    if is_expecting_empty:
        if not actual_log_lines:
            return
        raise AssertionError(f"Expected no application log output, but found lines:\n{actual_log_lines}")
    if not actual_log_lines:
        raise AssertionError(f"No application log lines found. Full Raw Output:\n{output}")

    found_match = False
    for line_str in actual_log_lines:
        validator = _validate_json_log_line if is_json else _validate_keyvalue_log_line
        if validator(line_str, expected_level, expected_message_core, expected_kvs, expect_timestamp):
            found_match = True
            break
    if expect_traceback_containing and not _check_traceback_presence(output, expect_traceback_containing):
        found_match = False
    if not found_match:
        raise AssertionError(f"Log line not found or format incorrect. Expected: level='{expected_level}', msg='{expected_message_core}', kvs={expected_kvs}. Full Output:\n{output}")

# These helpers are copied here to make this test file self-contained for this fix
def _validate_json_log_line(line: str, expected_level: str, expected_message: str, expected_kvs: dict[str, Any] | None = None, expect_timestamp: bool = True) -> bool:
    try:
        log_json = json.loads(line)
        if expect_timestamp:
            if "timestamp" not in log_json:
                return False
        else:
            if "timestamp" in log_json:
                return False
        if log_json.get("level") != expected_level.lower():
            return False
        if log_json.get("event") != expected_message:
            return False
        if expected_kvs:
            for k, v_expected in expected_kvs.items():
                if log_json.get(k) != v_expected:
                    return False
        return True
    except json.JSONDecodeError:
        return False

def _validate_keyvalue_log_line(line: str, expected_level: str, expected_message: str, expected_kvs: dict[str, Any] | None = None, expect_timestamp: bool = True) -> bool:
    has_timestamp = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}", line)
    if expect_timestamp and not has_timestamp:
        return False
    if not expect_timestamp and has_timestamp:
        return False
    if not re.search(rf"\[\s*{re.escape(expected_level)}\s*\]", line, re.IGNORECASE):
        return False
    # Check if the core message is a substring of the line
    if expected_message not in line:
        return False
    if expected_kvs:
        for k, v_expected in expected_kvs.items():
            val_str = str(v_expected) if not isinstance(v_expected, bool) else str(v_expected).lower()
            # Use regex to ensure it's a key=value pair and not just a substring
            if not re.search(rf"\b{re.escape(k)}={re.escape(val_str)}\b", line):
                return False
    return True

def _check_traceback_presence(output: str, expected_traceback: str) -> bool:
    return "Traceback (most recent call last):" in output and expected_traceback in output

class TestConfigWarnings:
    @pytest.mark.parametrize("module_levels_env, expected_warning_parts", [
        ("no_colon_module_level", ["Invalid item 'no_colon_module_level' in PYVIDER_LOG_MODULE_LEVELS. Skipping."]),
        (":DEBUG", ["Invalid item ':DEBUG' in PYVIDER_LOG_MODULE_LEVELS. Skipping."]),
        ("valid_module:SUPER_LEVEL", ["Invalid log level 'SUPER_LEVEL' for module 'valid_module'. Skipping."]),
        ("mod1:INFO,mod2:BOGUS,mod3:DEBUG", ["Invalid log level 'BOGUS' for module 'mod2'. Skipping."]),
        ("mod1:INFO,,mod3:DEBUG", []),
        ("mod1:INFO, :TRACE ,mod3:DEBUG", ["Invalid item ':TRACE' in PYVIDER_LOG_MODULE_LEVELS. Skipping."]),
    ])
    def test_invalid_pyvider_log_module_levels(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], module_levels_env: str, expected_warning_parts: list[str]) -> None:
        from pyvider.telemetry.config import (
            _ensure_config_logger_handler,
            config_warnings_logger,
        )
        monkeypatch.setenv("PYVIDER_LOG_MODULE_LEVELS", module_levels_env)
        _ensure_config_logger_handler(config_warnings_logger)
        TelemetryConfig.from_env()
        captured_err = capsys.readouterr().err
        if not expected_warning_parts:
            assert "[Pyvider Config Warning]" not in captured_err
        else:
            for part in expected_warning_parts:
                assert part in captured_err



class TestLoggingWithSemanticLayers:
    def test_llm_layer_end_to_end(self, setup_pyvider_telemetry_for_test: callable, captured_stderr_for_pyvider: "io.StringIO") -> None:
        config = TelemetryConfig(logging=LoggingConfig(enabled_semantic_layers=["llm"], console_formatter="key_value", das_emoji_prefix_enabled=True, logger_name_emoji_prefix_enabled=False))
        setup_pyvider_telemetry_for_test(config)
        global_logger.info("LLM generated response", **{"llm.provider": "openai", "llm.task": "generation", "llm.model": "gpt-4o", "llm.outcome": "success", "duration_ms": 1230, "llm.output.tokens": 250})
        output = captured_stderr_for_pyvider.getvalue()
        assert "[🤖][✍️][💡][👍] LLM generated response" in output
        assert "duration_ms=1230" in output
        assert "llm.output.tokens=250" in output
        assert "llm.provider=openai" not in output

    def test_legacy_das_still_works_if_no_layers_active(self, setup_pyvider_telemetry_for_test: callable, captured_stderr_for_pyvider: "io.StringIO") -> None:
        config = TelemetryConfig(logging=LoggingConfig(console_formatter="key_value", das_emoji_prefix_enabled=True, logger_name_emoji_prefix_enabled=False))
        setup_pyvider_telemetry_for_test(config)
        global_logger.info("Legacy system test", domain="auth", action="login", status="success")
        output = captured_stderr_for_pyvider.getvalue()
        assert "[🔑][➡️][✅] Legacy system test" in output
        assert "domain=auth" not in output
