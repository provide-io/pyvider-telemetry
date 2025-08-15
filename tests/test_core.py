#
# tests/test_core.py
#
"""
Unit tests for src.pyvider.telemetry.core.py
"""
import io
import logging as stdlib_logging
import sys
from unittest.mock import MagicMock, patch

import pytest
from pytest import CaptureFixture
import structlog

from pyvider.telemetry.config import (
    LoggingConfig,
    TelemetryConfig,
)
from pyvider.telemetry.core import (
    _CORE_SETUP_LOGGER_NAME,
    _create_core_setup_logger,
    _get_safe_stderr,
    _handle_globally_disabled_setup,
    reset_pyvider_setup_for_testing,
    setup_telemetry,
    shutdown_pyvider_telemetry,
)
from pyvider.telemetry.logger import base as logger_base_module


class TestGetSafeStderr:
    def test_get_safe_stderr_is_none(self) -> None:
        with patch.object(sys, 'stderr', None):
            fallback_stream = _get_safe_stderr()
            assert isinstance(fallback_stream, io.StringIO)

    def test_get_safe_stderr_is_valid(self) -> None:
        original_stderr = sys.stderr
        if original_stderr is None:
            sys.stderr = io.StringIO("temp stderr for test")
        try:
            if sys.stderr is not None:
                stream = _get_safe_stderr()
                assert stream == sys.stderr
            else: # pragma: no cover
                pytest.skip("sys.stderr was None, cannot run this specific path meaningfully.")
        finally:
            if original_stderr is None and hasattr(sys, 'stderr'):
                 sys.stderr = original_stderr

class TestCreateCoreSetupLogger:
    def test_create_core_setup_logger_handler_close_exception(self) -> None:
        logger = stdlib_logging.getLogger(_CORE_SETUP_LOGGER_NAME)
        original_handlers = list(logger.handlers)
        logger.handlers.clear()
        mock_handler_stream = io.StringIO()
        mock_handler = stdlib_logging.StreamHandler(mock_handler_stream)
        mock_handler.close = MagicMock(side_effect=RuntimeError("Failed to close"))
        logger.addHandler(mock_handler)
        try:
            _create_core_setup_logger(globally_disabled=False)
            assert mock_handler not in logger.handlers
            assert len(logger.handlers) == 1
        finally:
            logger.handlers.clear()
            for handler in original_handlers:
                logger.addHandler(handler)
            if not mock_handler_stream.closed:
                mock_handler_stream.close()

class TestStateResetCoverage:
    def test_reset_pyvider_setup_for_testing_resets_lazy_state(self) -> None:
        logger_base_module._LAZY_SETUP_STATE["done"] = True
        logger_base_module._LAZY_SETUP_STATE["error"] = Exception("dummy error")
        logger_base_module._LAZY_SETUP_STATE["in_progress"] = True
        reset_pyvider_setup_for_testing()
        assert not logger_base_module._LAZY_SETUP_STATE["done"]
        assert logger_base_module._LAZY_SETUP_STATE["error"] is None
        assert not logger_base_module._LAZY_SETUP_STATE["in_progress"]

    def test_setup_telemetry_resets_lazy_state(self) -> None:
        logger_base_module._LAZY_SETUP_STATE["done"] = True
        logger_base_module._LAZY_SETUP_STATE["error"] = Exception("dummy error")
        logger_base_module._LAZY_SETUP_STATE["in_progress"] = True
        basic_config = TelemetryConfig(logging=LoggingConfig(default_level="INFO"))
        setup_telemetry(basic_config)
        assert logger_base_module._LAZY_SETUP_STATE["done"]
        assert logger_base_module._LAZY_SETUP_STATE["error"] is None
        assert not logger_base_module._LAZY_SETUP_STATE["in_progress"]

class TestShutdownCoverage:
    @pytest.mark.asyncio
    async def test_shutdown_pyvider_telemetry_logs_message(self, capsys: CaptureFixture[str]) -> None:
        reset_pyvider_setup_for_testing()
        core_logger_for_shutdown_test = stdlib_logging.getLogger(_CORE_SETUP_LOGGER_NAME)
        core_logger_for_shutdown_test.setLevel(stdlib_logging.INFO)
        await shutdown_pyvider_telemetry()
        captured = capsys.readouterr()
        assert "Pyvider telemetry shutdown called" in captured.err

# FIX: Rewrote TestHandleGloballyDisabledSetup to be simpler and correct.
class TestHandleGloballyDisabledSetup:
    def test_globally_disabled_configures_structlog_as_noop(self, capsys: CaptureFixture[str]) -> None:
        """
        Tests that _handle_globally_disabled_setup configures structlog with ReturnLoggerFactory.
        """
        reset_pyvider_setup_for_testing() # Ensure clean state

        _handle_globally_disabled_setup()

        # Check that structlog is configured to be a no-op
        config = structlog.get_config()
        assert isinstance(config.get('logger_factory'), structlog.ReturnLoggerFactory)
        assert config.get('processors') == []

        # Check that the setup message was logged
        captured = capsys.readouterr()
        assert "Pyvider telemetry globally disabled." in captured.err
