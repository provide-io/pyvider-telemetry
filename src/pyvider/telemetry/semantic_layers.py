# src/pyvider/telemetry/semantic_layers.py
"""
Predefined Semantic Telemetry Layers for Pyvider Telemetry.

This module contains definitions for built-in semantic layers that provide
standardized logging conventions (structured keys, emojis) for common
technologies and domains like LLMs, HTTP interactions, and databases.
"""

from pyvider.telemetry.logger.emoji_matrix import (
    PRIMARY_EMOJI,
    SECONDARY_EMOJI,
    TERTIARY_EMOJI,
)
from pyvider.telemetry.types import (
    CustomDasEmojiSet,
    SemanticFieldDefinition,
    SemanticLayer,
)

# --- Base/Legacy Layer Definition (Internal representation) ---
# This serves as the fallback if no other layers are active or if active layers
# don't handle the specific keys "domain", "action", "status".
LEGACY_DAS_EMOJI_SETS: list[CustomDasEmojiSet] = [
    CustomDasEmojiSet(name="_legacy_domain", emojis=PRIMARY_EMOJI, default_emoji_key="default"),
    CustomDasEmojiSet(name="_legacy_action", emojis=SECONDARY_EMOJI, default_emoji_key="default"),
    CustomDasEmojiSet(name="_legacy_status", emojis=TERTIARY_EMOJI, default_emoji_key="default"),
]
LEGACY_DAS_FIELD_DEFINITIONS: list[SemanticFieldDefinition] = [
    SemanticFieldDefinition(log_key="domain", emoji_set_name="_legacy_domain"),
    SemanticFieldDefinition(log_key="action", emoji_set_name="_legacy_action"),
    SemanticFieldDefinition(log_key="status", emoji_set_name="_legacy_status"),
]
# Note: The legacy system is not a formal "SemanticLayer" that users enable by name.
# It's used as a fallback in the `add_das_emoji_prefix` processor.

# --- LLM Layer ---
LLM_EMOJI_SETS: list[CustomDasEmojiSet] = [
    CustomDasEmojiSet(
        name="llm_provider",
        emojis={"openai": "🤖", "anthropic": "📚", "google": "🇬", "meta": "🦙", "mistral": "🌬️", "perplexity": "❓", "cohere": "🔊", "default": "💡"},
        default_emoji_key="default"
    ),
    CustomDasEmojiSet(
        name="llm_task",
        emojis={"generation": "✍️", "completion": "✅", "embedding": "🔗", "chat": "💬", "tool_use": "🛠️", "summarization": "📜", "translation": "🌐", "classification": "🏷️", "default": "⚡"},
        default_emoji_key="default"
    ),
    CustomDasEmojiSet(
        name="llm_outcome",
        emojis={"success": "👍", "error": "🔥", "filtered_input": "🛡️👁️", "filtered_output": "🛡️🗣️", "rate_limit": "⏳", "partial_success": "🤏", "tool_call": "📞", "default": "➡️"},
        default_emoji_key="default"
    )
]
LLM_FIELD_DEFINITIONS: list[SemanticFieldDefinition] = [
    SemanticFieldDefinition(log_key="llm.provider", description="Name of the LLM provider (e.g., openai, anthropic)", value_type="string", emoji_set_name="llm_provider"),
    SemanticFieldDefinition(log_key="llm.task", description="The specific LLM task being performed (e.g., generation, chat)", value_type="string", emoji_set_name="llm_task"),
    SemanticFieldDefinition(log_key="llm.model", description="Identifier of the LLM model used", value_type="string", emoji_set_name="llm_provider"), # Reuses provider emojis for model by default
    SemanticFieldDefinition(log_key="llm.outcome", description="Outcome of the LLM operation", value_type="string", emoji_set_name="llm_outcome"),
    SemanticFieldDefinition(log_key="llm.input.tokens", description="Number of input tokens", value_type="integer"),
    SemanticFieldDefinition(log_key="llm.output.tokens", description="Number of output tokens", value_type="integer"),
    SemanticFieldDefinition(log_key="llm.tool.name", description="Name of the tool called by the LLM", value_type="string"),
    SemanticFieldDefinition(log_key="llm.tool.call_id", description="Identifier for a specific tool call", value_type="string"),
    SemanticFieldDefinition(log_key="duration_ms", description="Duration of the LLM operation in milliseconds", value_type="integer"),
    SemanticFieldDefinition(log_key="trace_id", description="Distributed trace ID for the operation", value_type="string"),
]
LLM_LAYER = SemanticLayer(
    name="llm",
    description="Semantic conventions for logging Large Language Model interactions.",
    emoji_sets=LLM_EMOJI_SETS,
    field_definitions=LLM_FIELD_DEFINITIONS,
    priority=100 # High priority
)

# --- Database Layer ---
DB_EMOJI_SETS: list[CustomDasEmojiSet] = [
    CustomDasEmojiSet(
        name="db_system",
        emojis={"postgres": "🐘", "mysql": "🐬", "sqlite": "💾", "mongodb": "🍃", "redis": "🟥", "elasticsearch": "🔍", "default": "🗄️"},
        default_emoji_key="default"
    ),
    CustomDasEmojiSet(
        name="db_operation",
        emojis={"query": "🔍", "select": "🔍", "insert": "➕", "update": "🔄", "delete": "🗑️", "connect": "🔗", "disconnect": "💔", "transaction_begin": "💳🟢", "transaction_commit": "💳✅", "transaction_rollback": "💳❌", "default": "⚙️"},
        default_emoji_key="default"
    ),
    CustomDasEmojiSet( # Can reuse llm_outcome or define specific DB outcomes
        name="db_outcome",
        emojis={"success": "👍", "error": "🔥", "not_found": "❓🤷", "timeout": "⏱️", "default": "➡️"},
        default_emoji_key="default"
    )
]
DB_FIELD_DEFINITIONS: list[SemanticFieldDefinition] = [
    SemanticFieldDefinition(log_key="db.system", description="Type of database system (e.g., postgres, mysql)", value_type="string", emoji_set_name="db_system"),
    SemanticFieldDefinition(log_key="db.operation", description="Database operation performed (e.g., query, insert)", value_type="string", emoji_set_name="db_operation"),
    SemanticFieldDefinition(log_key="db.statement", description="The database statement executed (potentially truncated/sanitized)", value_type="string"),
    SemanticFieldDefinition(log_key="db.table", description="Name of the database table involved", value_type="string", emoji_set_name="db_system", default_emoji_override_key="default"), # Use default DB emoji
    SemanticFieldDefinition(log_key="db.rows_affected", description="Number of rows affected by the operation", value_type="integer"),
    SemanticFieldDefinition(log_key="db.outcome", description="Outcome of the database operation", value_type="string", emoji_set_name="db_outcome"),
    SemanticFieldDefinition(log_key="duration_ms", description="Duration of the database operation in milliseconds", value_type="integer"),
    SemanticFieldDefinition(log_key="trace_id", description="Distributed trace ID for the operation", value_type="string"),
]
DATABASE_LAYER = SemanticLayer(
    name="database",
    description="Semantic conventions for logging database interactions.",
    emoji_sets=DB_EMOJI_SETS,
    field_definitions=DB_FIELD_DEFINITIONS,
    priority=90
)

# --- HTTP Layer (Client/Server) ---
HTTP_EMOJI_SETS: list[CustomDasEmojiSet] = [
    CustomDasEmojiSet(
        name="http_method",
        emojis={"get": "📥", "post": "📤", "put": "📝⬆️", "delete": "🗑️", "patch":"🩹", "head": "👤❔", "options": "⚙️❔", "default": "🌐"},
        default_emoji_key="default"
    ),
    CustomDasEmojiSet(
        name="http_status_class", # For 2xx, 3xx etc.
        emojis={"1xx": "ℹ️", "2xx": "✅", "3xx": "↪️", "4xx": "⚠️CLIENT", "5xx": "🔥SERVER", "default": "❓"},
        default_emoji_key="default"
    ),
    CustomDasEmojiSet(
        name="http_target_type", # For path, query, fragment
        emojis={"path": "🛣️", "query": "❓", "fragment": "#️⃣", "default": "🎯"},
        default_emoji_key="default"
    )
]
HTTP_FIELD_DEFINITIONS: list[SemanticFieldDefinition] = [
    SemanticFieldDefinition(log_key="http.method", description="HTTP request method (e.g., GET, POST)", value_type="string", emoji_set_name="http_method"),
    SemanticFieldDefinition(log_key="http.url", description="Full HTTP URL of the request", value_type="string"),
    SemanticFieldDefinition(log_key="http.target", description="Request target (path and query string)", value_type="string", emoji_set_name="http_target_type", default_emoji_override_key="path"),
    SemanticFieldDefinition(log_key="http.scheme", description="URL scheme (e.g., http, https)", value_type="string"),
    SemanticFieldDefinition(log_key="http.host", description="Hostname of the request", value_type="string"),
    SemanticFieldDefinition(log_key="http.status_code", description="HTTP response status code", value_type="integer"),
    SemanticFieldDefinition(log_key="http.status_class", description="HTTP status code class (e.g., 2xx, 4xx)", value_type="string", emoji_set_name="http_status_class"),
    SemanticFieldDefinition(log_key="http.request.body.size", description="Size of HTTP request body in bytes", value_type="integer"),
    SemanticFieldDefinition(log_key="http.response.body.size", description="Size of HTTP response body in bytes", value_type="integer"),
    SemanticFieldDefinition(log_key="client.address", description="Client IP address", value_type="string"),
    SemanticFieldDefinition(log_key="server.address", description="Server IP address or hostname", value_type="string"),
    SemanticFieldDefinition(log_key="duration_ms", description="Duration of the HTTP request/response cycle in milliseconds", value_type="integer"),
    SemanticFieldDefinition(log_key="trace_id", description="Distributed trace ID for the operation", value_type="string"),
    SemanticFieldDefinition(log_key="span_id", description="Span ID for the operation", value_type="string"),
    SemanticFieldDefinition(log_key="error.message", description="Error message if request failed", value_type="string"),
    SemanticFieldDefinition(log_key="error.type", description="Type of error if request failed", value_type="string"),
]
HTTP_LAYER = SemanticLayer(
    name="http",
    description="Semantic conventions for logging HTTP client and server interactions.",
    emoji_sets=HTTP_EMOJI_SETS,
    field_definitions=HTTP_FIELD_DEFINITIONS,
    priority=80
)

# --- Task Queue Layer ---
TASK_QUEUE_EMOJI_SETS: list[CustomDasEmojiSet] = [
    CustomDasEmojiSet(name="task_system", emojis={"celery": "🥕", "rq": "🟥🇶", "dramatiq": "🎭", "kafka": "🌊", "rabbitmq": "🐇", "default": "📨"}, default_emoji_key="default"),
    CustomDasEmojiSet(name="task_status", emojis={"submitted": "➡️📨", "received": "📥", "started": "▶️", "progress": "🔄", "retrying": "🔁", "success": "✅🏁", "failure": "❌🔥", "revoked": "🚫", "default": "❓"}, default_emoji_key="default")
]
TASK_QUEUE_FIELD_DEFINITIONS: list[SemanticFieldDefinition] = [
    SemanticFieldDefinition(log_key="task.system", description="Task queue system used (e.g., celery, rq)", value_type="string", emoji_set_name="task_system"),
    SemanticFieldDefinition(log_key="task.id", description="Unique identifier for the task instance", value_type="string"),
    SemanticFieldDefinition(log_key="task.name", description="Name of the task or job", value_type="string"),
    SemanticFieldDefinition(log_key="task.queue_name", description="Name of the queue the task was processed on", value_type="string"),
    SemanticFieldDefinition(log_key="task.status", description="Current status of the task", value_type="string", emoji_set_name="task_status"),
    SemanticFieldDefinition(log_key="task.retries", description="Number of retries for the task", value_type="integer"),
    SemanticFieldDefinition(log_key="duration_ms", description="Execution duration of the task in milliseconds", value_type="integer"),
    SemanticFieldDefinition(log_key="trace_id", description="Distributed trace ID associated with the task", value_type="string"),
]
TASK_QUEUE_LAYER = SemanticLayer(
    name="task_queue",
    description="Semantic conventions for logging asynchronous task queue operations.",
    emoji_sets=TASK_QUEUE_EMOJI_SETS,
    field_definitions=TASK_QUEUE_FIELD_DEFINITIONS,
    priority=70
)


# Registry of all built-in layers
BUILTIN_SEMANTIC_LAYERS: dict[str, SemanticLayer] = {
    LLM_LAYER.name: LLM_LAYER,
    DATABASE_LAYER.name: DATABASE_LAYER,
    HTTP_LAYER.name: HTTP_LAYER,
    TASK_QUEUE_LAYER.name: TASK_QUEUE_LAYER,
    # Add more layers here (e.g., FILE_IO_LAYER, RPC_LAYER)
}
