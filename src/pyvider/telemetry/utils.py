# src/pyvider/telemetry/utils.py
"""
Utility functions for Pyvider Telemetry, such as context managers for timing operations.
"""
from collections.abc import Generator
from contextlib import contextmanager
import contextvars  # For potential trace_id integration
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyvider.telemetry.logger.base import PyviderLogger


# Example context variable for trace_id (application would need to set this)
# This is just a placeholder to show how it *could* be integrated.
# Pyvider Telemetry itself won't manage this contextvar's lifecycle.
_PYVIDER_CONTEXT_TRACE_ID = contextvars.ContextVar("pyvider_context_trace_id", default=None)


@contextmanager
def timed_block(
    logger_instance: "PyviderLogger",
    event_name: str,
    # Semantic keys for layers (examples, actual keys depend on active layers)
    # These are just illustrative; the user provides relevant semantic keys.
    layer_keys: dict[str, Any] | None = None,
    **initial_kvs: Any
) -> Generator[None, None, None]:
    """
    A context manager to log the duration and outcome of a block of code.

    It automatically captures the start time, executes the wrapped code block,
    and then logs an event including the duration, outcome (success/error),
    and any initial or error-specific key-value pairs.

    Args:
        logger_instance: The PyviderLogger instance to use for logging.
        event_name: A descriptive name for the event/operation being timed.
        layer_keys: Optional dictionary of pre-defined semantic keys relevant to
                    active telemetry layers (e.g., {"llm.task": "generation"}).
                    These are merged with initial_kvs.
        **initial_kvs: Additional key-value pairs to include in the log entry
                       from the start of the block.

    Example:
        ```python
        from pyvider.telemetry import logger
        from pyvider.telemetry.utils import timed_block

        with timed_block(logger, "database_query", db_operation="select_user", db_table="users"):
            # ... code to execute database query ...
            if error_condition:
                raise ValueError("Simulated DB error")
        ```
    """
    start_time = time.perf_counter()

    log_kvs = initial_kvs.copy()
    if layer_keys:
        log_kvs.update(layer_keys)

    # Attempt to get trace_id from contextvar if a standard key is conventional
    # This part is highly dependent on how an application manages trace_id.
    # For now, we'll assume if "trace_id" is a known semantic key, it might be in context.
    # A more robust solution would involve integration with a tracing library.
    contextual_trace_id = _PYVIDER_CONTEXT_TRACE_ID.get()
    if contextual_trace_id and "trace_id" not in log_kvs: # Only add if not already provided
        log_kvs["trace_id"] = contextual_trace_id

    # Default outcome key, can be overridden by layer_keys or initial_kvs
    # Or, a layer could define a standard key like "operation.outcome"
    outcome_key = "outcome" # Generic outcome key

    try:
        yield # User's code block runs here
        log_kvs[outcome_key] = "success"
    except Exception as e:
        log_kvs[outcome_key] = "error"
        # Standardized error keys (could be part of a "base" or "error" semantic layer)
        log_kvs["error.message"] = str(e)
        log_kvs["error.type"] = type(e).__name__
        # Consider adding traceback if logger_instance.exception is used,
        # but timed_block is more for info/error level.
        # For exceptions, it's often better to catch and log with logger.exception()
        # directly in the user's code if full traceback is needed.
        raise # Re-raise the exception after capturing info
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_kvs["duration_ms"] = int(duration_ms)

        # Determine log level based on outcome
        final_outcome = log_kvs.get(outcome_key)
        if final_outcome == "error":
            logger_instance.error(event_name, **log_kvs)
        elif final_outcome == "success":
            logger_instance.info(event_name, **log_kvs)
        else: # Other outcomes or if outcome key was changed
            logger_instance.info(event_name, **log_kvs) # pragma: no cover

# ⏱️🪵
