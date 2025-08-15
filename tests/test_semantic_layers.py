# tests/test_semantic_layers.py
"""
Tests for Semantic Layer configuration, resolution, and processing.
"""
from collections.abc import Callable
import io

import pytest

from pyvider.telemetry import (
    LoggingConfig,
    TelemetryConfig,
    logger as global_logger,
)
from pyvider.telemetry.core import (
    _resolve_active_semantic_config,
    reset_pyvider_setup_for_testing,
)
from pyvider.telemetry.semantic_layers import (
    BUILTIN_SEMANTIC_LAYERS,
    HTTP_LAYER,
    LEGACY_DAS_EMOJI_SETS,
    LLM_LAYER,
)
from pyvider.telemetry.types import (
    CustomDasEmojiSet,
    SemanticFieldDefinition,
    SemanticLayer,
)

ResolvedSemanticConfigForTest = tuple[list[SemanticFieldDefinition], dict[str, CustomDasEmojiSet]]

@pytest.fixture(autouse=True)
def auto_reset_telemetry():
    reset_pyvider_setup_for_testing()
    yield
    reset_pyvider_setup_for_testing()

class TestResolveActiveSemanticConfig:
    def test_no_layers_enabled(self):
        lc = LoggingConfig()
        resolved_fields, resolved_emoji_sets = _resolve_active_semantic_config(lc, BUILTIN_SEMANTIC_LAYERS)
        assert resolved_fields == []
        for les in LEGACY_DAS_EMOJI_SETS:
            assert les.name in resolved_emoji_sets

    def test_enable_multiple_builtin_layers_no_conflict(self):
        lc = LoggingConfig(enabled_semantic_layers=["llm", "http"])
        resolved_fields, resolved_emoji_sets = _resolve_active_semantic_config(lc, BUILTIN_SEMANTIC_LAYERS)
        llm_field_keys = {f.log_key for f in LLM_LAYER.field_definitions}
        http_field_keys = {f.log_key for f in HTTP_LAYER.field_definitions}
        expected_field_count = len(llm_field_keys.union(http_field_keys))
        assert len(resolved_fields) == expected_field_count
        assert "llm_provider" in resolved_emoji_sets and "http_method" in resolved_emoji_sets

    def test_layer_priority_for_field_definitions(self):
        field1 = SemanticFieldDefinition(log_key="shared_key", description="from layer1")
        layer1 = SemanticLayer(name="layer1", field_definitions=[field1], priority=10)
        field2 = SemanticFieldDefinition(log_key="shared_key", description="from layer2")
        layer2 = SemanticLayer(name="layer2", field_definitions=[field2], priority=20)
        lc = LoggingConfig(custom_semantic_layers=[layer1, layer2])
        resolved_fields, _ = _resolve_active_semantic_config(lc, {})
        assert len(resolved_fields) == 1 and resolved_fields[0].description == "from layer2"

class TestSetupWithLayers:
    def _filter_app_logs(self, output: str) -> str:
        return "\n".join([line for line in output.splitlines() if not line.startswith("[Pyvider Setup]")])

    def test_setup_with_enabled_llm_layer(
        self,
        setup_pyvider_telemetry_for_test: Callable[[TelemetryConfig | None], None],
        captured_stderr_for_pyvider: io.StringIO,
    ) -> None:
        config = TelemetryConfig(logging=LoggingConfig(enabled_semantic_layers=["llm"], console_formatter="key_value", das_emoji_prefix_enabled=True, logger_name_emoji_prefix_enabled=False))
        setup_pyvider_telemetry_for_test(config)
        global_logger.info("LLM Generation", **{"llm.provider": "openai", "llm.task": "generation", "llm.outcome": "success"})
        captured = self._filter_app_logs(captured_stderr_for_pyvider.getvalue())
        assert "[🤖][✍️][👍] LLM Generation" in captured

    def test_setup_with_custom_layer_overriding_builtin_emojis(
        self,
        setup_pyvider_telemetry_for_test: Callable[[TelemetryConfig | None], None],
        captured_stderr_for_pyvider: io.StringIO,
    ) -> None:
        my_llm_provider_emojis = CustomDasEmojiSet(name="llm_provider", emojis={"openai": "🧠MAX", "default": "💡CUST"})
        config = TelemetryConfig(logging=LoggingConfig(enabled_semantic_layers=["llm"], user_defined_emoji_sets=[my_llm_provider_emojis], console_formatter="key_value", das_emoji_prefix_enabled=True, logger_name_emoji_prefix_enabled=False))
        setup_pyvider_telemetry_for_test(config)
        global_logger.info("LLM Call", **{"llm.provider": "openai", "llm.task": "chat", "llm.outcome": "error"})
        captured = self._filter_app_logs(captured_stderr_for_pyvider.getvalue())
        assert "[🧠MAX][💬][🔥] LLM Call" in captured

    def test_env_var_parsing_for_layers(
        self,
        monkeypatch: pytest.MonkeyPatch,
        setup_pyvider_telemetry_for_test: Callable[[TelemetryConfig | None], None],
        captured_stderr_for_pyvider: io.StringIO,
    ) -> None:
        monkeypatch.setenv("PYVIDER_LOG_ENABLED_SEMANTIC_LAYERS", "http")
        monkeypatch.setenv("PYVIDER_LOG_USER_DEFINED_EMOJI_SETS", '[{"name": "http_method", "emojis": {"get": "🔽", "default": "🌐"}}]')
        monkeypatch.setenv("PYVIDER_LOG_LOGGER_NAME_EMOJI_ENABLED", "false")
        setup_pyvider_telemetry_for_test(TelemetryConfig.from_env())
        global_logger.info("HTTP GET", **{"http.method": "get", "http.status_class": "2xx"})
        captured = self._filter_app_logs(captured_stderr_for_pyvider.getvalue())
        assert "[🔽][✅] HTTP GET" in captured
