#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovZ_Communication
Module: TradovZ02_MessageProtocol.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from typing import Any

try:
    import orjson as _orjson  # 3-10x faster JSON serialization
    def _json_dumps(obj) -> bytes:
        return _orjson.dumps(obj)
    def _json_loads(data) -> Any:
        return _orjson.loads(data)
except ImportError:
    import json as _json_std
    def _json_dumps(obj) -> bytes:  # type: ignore[misc]
        return _json_std.dumps(obj).encode('utf-8')
    def _json_loads(data) -> Any:  # type: ignore[misc]
        return _json_std.loads(data)
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
import uuid
from collections import defaultdict
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import zlib
import hashlib
import jsonschema
from jsonschema import ValidationError

try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    logging.getLogger(__name__).debug("msgpack not installed. Using JSON serialization.")

# Optional encryption
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    warnings.warn("cryptography not installed. Encryption disabled.", stacklevel=2)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Protocol versions
PROTOCOL_VERSION = "2.0"
MIN_SUPPORTED_VERSION = "1.0"
PROTOCOL_VERSIONS = ["1.0", "1.1", "2.0"]

# Serialization settings
COMPRESSION_THRESHOLD = 1024  # bytes
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB

# Validation settings
STRICT_VALIDATION = True
VALIDATE_TIMESTAMPS = True
MAX_FUTURE_TIMESTAMP = 60  # seconds

# Agent handoff contract settings
AGENT_HANDOFF_SCHEMA_VERSION = "1.0"
AGENT_HANDOFF_SCHEMA_NAMES = {
    "AGENT_HANDOFF_V1",
    "AGENT_DECISION_V1",
    "AGENT_ESCALATION_V1",
}

# Message priority levels
PRIORITY_CRITICAL = 10
PRIORITY_HIGH = 8
PRIORITY_NORMAL = 5
PRIORITY_LOW = 3
PRIORITY_BACKGROUND = 1

# ==============================================================================
# ENUMS
# ==============================================================================
class SerializationFormat(Enum):
    """Serialization formats with compression support."""
    JSON = "json"
    MSGPACK = "msgpack"
    COMPRESSED_JSON = "compressed_json"
    COMPRESSED_MSGPACK = "compressed_msgpack"
    ENCRYPTED_JSON = "encrypted_json"
    ENCRYPTED_MSGPACK = "encrypted_msgpack"

class MessageCategory(Enum):
    """High-level message categories."""
    MARKET = "MARKET"
    TRADE = "TRADE"
    RISK = "RISK"
    SYSTEM = "SYSTEM"
    STRATEGY = "STRATEGY"
    ACCOUNT = "ACCOUNT"
    ALERT = "ALERT"
    SECURITY = "SECURITY"

class ValidationLevel(Enum):
    """Message validation levels."""
    NONE = 0
    BASIC = 1
    STANDARD = 2
    STRICT = 3

# ==============================================================================
# SCHEMAS
# ==============================================================================
class MessageSchemas:
    """JSON schemas for message validation."""

    # Base message schema
    BASE_MESSAGE = {
        "type": "object",
        "required": ["version", "category", "type", "timestamp", "source", "data"],
        "properties": {
            "version": {
                "type": "string",
                "pattern": r"^\d+\.\d+$"
            },
            "category": {
                "type": "string",
                "enum": [cat.value for cat in MessageCategory]
            },
            "type": {
                "type": "string",
                "minLength": 1,
                "maxLength": 50
            },
            "timestamp": {
                "type": "number",
                "minimum": 0
            },
            "source": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100
            },
            "destination": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100
            },
            "correlation_id": {
                "type": ["string", "null"]
            },
            "message_id": {
                "type": "string"
            },
            "priority": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10
            },
            "data": {
                "type": "object"
            },
            "metadata": {
                "type": "object"
            }
        }
    }

    # Market data schema
    MARKET_DATA = {
        "type": "object",
        "required": ["symbol", "timestamp"],
        "properties": {
            "symbol": {
                "type": "string",
                "pattern": r"^[A-Z0-9]+$"
            },
            "timestamp": {
                "type": "number"
            },
            "bid": {
                "type": ["number", "null"],
                "minimum": 0
            },
            "ask": {
                "type": ["number", "null"],
                "minimum": 0
            },
            "last": {
                "type": ["number", "null"],
                "minimum": 0
            },
            "volume": {
                "type": ["integer", "null"],
                "minimum": 0
            },
            "bid_size": {
                "type": ["integer", "null"],
                "minimum": 0
            },
            "ask_size": {
                "type": ["integer", "null"],
                "minimum": 0
            }
        }
    }

    # Order schema
    ORDER = {
        "type": "object",
        "required": ["symbol", "action", "quantity", "order_type"],
        "properties": {
            "order_id": {
                "type": "string"
            },
            "symbol": {
                "type": "string"
            },
            "action": {
                "type": "string",
                "enum": ["BUY", "SELL"]
            },
            "quantity": {
                "type": "integer",
                "minimum": 1
            },
            "order_type": {
                "type": "string",
                "enum": ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
            },
            "price": {
                "type": ["number", "null"],
                "minimum": 0
            },
            "stop_price": {
                "type": ["number", "null"],
                "minimum": 0
            },
            "time_in_force": {
                "type": "string",
                "enum": ["DAY", "GTC", "IOC", "FOK"]
            }
        }
    }

    # Risk metrics schema
    RISK_METRICS = {
        "type": "object",
        "required": ["timestamp"],
        "properties": {
            "timestamp": {
                "type": "number"
            },
            "portfolio_delta": {
                "type": ["number", "null"]
            },
            "portfolio_gamma": {
                "type": ["number", "null"]
            },
            "portfolio_theta": {
                "type": ["number", "null"]
            },
            "portfolio_vega": {
                "type": ["number", "null"]
            },
            "portfolio_value": {
                "type": ["number", "null"],
                "minimum": 0
            },
            "var_95": {
                "type": ["number", "null"]
            },
            "max_drawdown": {
                "type": ["number", "null"]
            }
        }
    }

    # Agent handoff schema (generic envelope)
    AGENT_HANDOFF_V1 = {
        "type": "object",
        "required": [
            "schema",
            "schema_version",
            "handoff_type",
            "topic",
            "producer",
            "timestamp",
            "payload",
        ],
        "properties": {
            "schema": {
                "const": "AGENT_HANDOFF_V1",
            },
            "schema_version": {
                "type": "string",
                "const": AGENT_HANDOFF_SCHEMA_VERSION,
            },
            "handoff_type": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
            },
            "topic": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
            },
            "producer": {
                "type": "object",
                "required": ["agent_id"],
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                    "agent_role": {"type": "string"},
                    "agent_class": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "timestamp": {
                "type": "number",
                "minimum": 0,
            },
            "payload": {
                "type": "object",
            },
            "confidence": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 1,
            },
            "reasoning": {
                "type": "string",
            },
            "trace": {
                "type": "object",
            },
            "context": {
                "type": "object",
            },
            "legacy_payload": {
                "type": "object",
            },
        },
    }

    # Agent decision schema (execution-adjacent intent)
    AGENT_DECISION_V1 = {
        "type": "object",
        "required": [
            "schema",
            "schema_version",
            "handoff_type",
            "topic",
            "producer",
            "timestamp",
            "payload",
            "decision",
        ],
        "properties": {
            "schema": {
                "const": "AGENT_DECISION_V1",
            },
            "schema_version": {
                "type": "string",
                "const": AGENT_HANDOFF_SCHEMA_VERSION,
            },
            "handoff_type": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
            },
            "topic": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
            },
            "producer": {
                "type": "object",
                "required": ["agent_id"],
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                    "agent_role": {"type": "string"},
                    "agent_class": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "timestamp": {
                "type": "number",
                "minimum": 0,
            },
            "payload": {
                "type": "object",
            },
            "decision": {
                "type": "object",
                "required": ["action", "confidence"],
                "properties": {
                    "action": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "reasoning": {
                        "type": "string",
                    },
                },
            },
            "confidence": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 1,
            },
            "reasoning": {
                "type": "string",
            },
            "trace": {
                "type": "object",
            },
            "context": {
                "type": "object",
            },
            "legacy_payload": {
                "type": "object",
            },
        },
    }

    # Agent escalation schema (human/operator escalation intent)
    AGENT_ESCALATION_V1 = {
        "type": "object",
        "required": [
            "schema",
            "schema_version",
            "handoff_type",
            "topic",
            "producer",
            "timestamp",
            "payload",
            "escalation",
        ],
        "properties": {
            "schema": {
                "const": "AGENT_ESCALATION_V1",
            },
            "schema_version": {
                "type": "string",
                "const": AGENT_HANDOFF_SCHEMA_VERSION,
            },
            "handoff_type": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
            },
            "topic": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
            },
            "producer": {
                "type": "object",
                "required": ["agent_id"],
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                    "agent_role": {"type": "string"},
                    "agent_class": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "timestamp": {
                "type": "number",
                "minimum": 0,
            },
            "payload": {
                "type": "object",
            },
            "escalation": {
                "type": "object",
                "required": ["severity", "reason"],
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "reason": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "target": {
                        "type": "string",
                    },
                },
            },
            "confidence": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 1,
            },
            "reasoning": {
                "type": "string",
            },
            "trace": {
                "type": "object",
            },
            "context": {
                "type": "object",
            },
            "legacy_payload": {
                "type": "object",
            },
        },
    }

# ==============================================================================
# MESSAGE TYPES
# ==============================================================================
@dataclass
class MessageMetadata:
    """Metadata for message tracking and debugging."""
    created_at: float = field(default_factory=time.time)
    version: str = PROTOCOL_VERSION
    compression: str | None = None
    encryption: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    route: list[str] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)

@dataclass
class ProtocolMessage:
    """Enhanced protocol message with validation."""
    category: MessageCategory
    message_type: str
    source: str
    data: dict[str, Any]
    destination: str | None = None
    correlation_id: str | None = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    priority: int = PRIORITY_NORMAL
    metadata: MessageMetadata = field(default_factory=MessageMetadata)

    def __post_init__(self):
        """Validate message after initialization."""
        if not isinstance(self.category, MessageCategory):
            self.category = MessageCategory(self.category)

        # Validate timestamp
        if VALIDATE_TIMESTAMPS:
            current_time = time.time()
            if self.timestamp > current_time + MAX_FUTURE_TIMESTAMP:
                raise ValueError(f"Timestamp too far in future: {self.timestamp}")
            if self.timestamp < 0:
                raise ValueError(f"Invalid timestamp: {self.timestamp}")

        # Validate priority
        if not 1 <= self.priority <= 10:
            raise ValueError(f"Priority must be between 1 and 10: {self.priority}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.metadata.version,
            "category": self.category.value,
            "type": self.message_type,
            "source": self.source,
            "destination": self.destination,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "metadata": asdict(self.metadata)
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ProtocolMessage':
        """Create from dictionary."""
        metadata_dict = data.pop("metadata", {})
        metadata = MessageMetadata(**metadata_dict)

        return cls(
            category=MessageCategory(data["category"]),
            message_type=data["type"],
            source=data["source"],
            destination=data.get("destination"),
            data=data["data"],
            correlation_id=data.get("correlation_id"),
            message_id=data.get("message_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", time.time()),
            priority=data.get("priority", PRIORITY_NORMAL),
            metadata=metadata
        )

# ==============================================================================
# SCHEMA VALIDATOR
# ==============================================================================
class SchemaValidator:
    """Schema validation with caching and performance optimization."""

    def __init__(self):
        self.schemas = {}
        self.validators = {}
        self._load_schemas()

    def _load_schemas(self):
        """Load all schemas."""
        self.schemas["BASE"] = MessageSchemas.BASE_MESSAGE
        self.schemas["MARKET_DATA"] = MessageSchemas.MARKET_DATA
        self.schemas["ORDER"] = MessageSchemas.ORDER
        self.schemas["RISK_METRICS"] = MessageSchemas.RISK_METRICS
        self.schemas["AGENT_HANDOFF_V1"] = MessageSchemas.AGENT_HANDOFF_V1
        self.schemas["AGENT_DECISION_V1"] = MessageSchemas.AGENT_DECISION_V1
        self.schemas["AGENT_ESCALATION_V1"] = MessageSchemas.AGENT_ESCALATION_V1

        # Create validators
        for name, schema in self.schemas.items():
            self.validators[name] = jsonschema.Draft7Validator(schema)

    def validate(self, data: dict[str, Any], schema_name: str) -> tuple[bool, str | None]:
        """
        Validate data against schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if schema_name not in self.validators:
            return False, f"Unknown schema: {schema_name}"

        try:
            self.validators[schema_name].validate(data)
            return True, None
        except ValidationError as e:
            return False, str(e)

    def validate_message(self, message: ProtocolMessage) -> tuple[bool, str | None]:
        """Validate a protocol message."""
        # First validate base message structure
        message_dict = message.to_dict()
        valid, error = self.validate(message_dict, "BASE")

        if not valid:
            return False, f"Base validation failed: {error}"

        # Then validate data based on message type
        if message.message_type == "MARKET_DATA":
            return self.validate(message.data, "MARKET_DATA")
        elif message.message_type in ["ORDER", "TRADE_ORDER"]:
            return self.validate(message.data, "ORDER")
        elif message.message_type == "RISK_UPDATE":
            return self.validate(message.data, "RISK_METRICS")

        return True, None

    def validate_agent_handoff_envelope(
        self,
        envelope: dict[str, Any],
        schema_name: str | None = None,
    ) -> tuple[bool, str | None]:
        """Validate an agent handoff envelope against V1 schemas."""
        if not isinstance(envelope, dict):
            return False, "Envelope must be a dictionary"

        resolved_schema = schema_name or str(envelope.get("schema", "")).strip()
        if not resolved_schema:
            resolved_schema = "AGENT_HANDOFF_V1"

        if resolved_schema not in AGENT_HANDOFF_SCHEMA_NAMES:
            return False, f"Unknown agent handoff schema: {resolved_schema}"

        return self.validate(envelope, resolved_schema)


_schema_validator_singleton: SchemaValidator | None = None


def _get_schema_validator() -> SchemaValidator:
    """Return a module-level singleton validator for hot-path helpers."""
    global _schema_validator_singleton
    if _schema_validator_singleton is None:
        _schema_validator_singleton = SchemaValidator()
    return _schema_validator_singleton


def extract_agent_handoff_envelope(
    payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Extract a handoff envelope from payload while preserving legacy shape support."""
    if not isinstance(payload, dict):
        return None, None

    schema_name = payload.get("schema")
    if isinstance(schema_name, str) and schema_name in AGENT_HANDOFF_SCHEMA_NAMES:
        return payload, schema_name

    for key in ("agent_handoff", "agent_handoff_v1", "handoff", "handoff_envelope"):
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            candidate_schema = candidate.get("schema")
            if isinstance(candidate_schema, str):
                return candidate, candidate_schema
            return candidate, None

    nested_data = payload.get("data")
    if isinstance(nested_data, dict) and nested_data is not payload:
        return extract_agent_handoff_envelope(nested_data)

    return None, None


def validate_agent_handoff_envelope(
    envelope: dict[str, Any],
    schema_name: str | None = None,
) -> tuple[bool, str | None]:
    """Validate a handoff envelope using a cached schema validator."""
    validator = _get_schema_validator()
    return validator.validate_agent_handoff_envelope(envelope, schema_name)


def build_agent_handoff_envelope(
    *,
    topic: str,
    producer_agent_id: str,
    payload: dict[str, Any],
    handoff_type: str = "handoff",
    schema: str = "AGENT_HANDOFF_V1",
    confidence: float | None = None,
    reasoning: str = "",
    producer_role: str | None = None,
    producer_class: str | None = None,
    context: dict[str, Any] | None = None,
    trace: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    escalation: dict[str, Any] | None = None,
    legacy_payload: dict[str, Any] | None = None,
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Build a normalized V1 agent handoff envelope for shadow-mode rollout."""
    if schema not in AGENT_HANDOFF_SCHEMA_NAMES:
        raise ValueError(f"Unsupported handoff schema: {schema}")

    producer = {
        "agent_id": producer_agent_id,
    }
    if producer_role:
        producer["agent_role"] = producer_role
    if producer_class:
        producer["agent_class"] = producer_class

    envelope: dict[str, Any] = {
        "schema": schema,
        "schema_version": AGENT_HANDOFF_SCHEMA_VERSION,
        "handoff_type": handoff_type,
        "topic": topic,
        "producer": producer,
        "timestamp": float(timestamp if timestamp is not None else time.time()),
        "payload": payload,
        "confidence": confidence,
        "reasoning": reasoning or "",
    }

    if context:
        envelope["context"] = context
    if trace:
        envelope["trace"] = trace
    if legacy_payload is not None:
        envelope["legacy_payload"] = legacy_payload

    if schema == "AGENT_DECISION_V1":
        fallback_decision = {
            "action": "unknown",
            "confidence": float(confidence or 0.0),
            "reasoning": reasoning or "",
        }
        envelope["decision"] = decision or fallback_decision

    if schema == "AGENT_ESCALATION_V1":
        fallback_escalation = {
            "severity": "medium",
            "reason": reasoning or "escalation_requested",
        }
        envelope["escalation"] = escalation or fallback_escalation

    return envelope

# ==============================================================================
# SERIALIZATION MANAGER
# ==============================================================================
class SerializationManager:
    """Handles message serialization with compression and encryption."""

    def __init__(self,
                 default_format: SerializationFormat = SerializationFormat.COMPRESSED_JSON,
                 encryption_key: bytes | None = None):
        self.default_format = default_format
        self.encryption_key = encryption_key
        self.fernet = None

        if encryption_key and ENCRYPTION_AVAILABLE:
            self.fernet = Fernet(encryption_key)

        self.logger = logging.getLogger("SerializationManager")

    def serialize(self,
                  message: ProtocolMessage,
                  format: SerializationFormat | None = None) -> bytes:
        """Serialize message to bytes."""
        format = format or self.default_format

        # Convert to dict
        data = message.to_dict()

        # Choose serialization method
        if format in [SerializationFormat.JSON, SerializationFormat.COMPRESSED_JSON,
                      SerializationFormat.ENCRYPTED_JSON]:
            serialized = _json_dumps(data)
        elif MSGPACK_AVAILABLE and format in [SerializationFormat.MSGPACK,
                                               SerializationFormat.COMPRESSED_MSGPACK,
                                               SerializationFormat.ENCRYPTED_MSGPACK]:
            serialized = msgpack.packb(data)
        else:
            # Fallback to JSON
            serialized = _json_dumps(data)

        # Apply compression if needed
        if format in [SerializationFormat.COMPRESSED_JSON, SerializationFormat.COMPRESSED_MSGPACK]:
            if len(serialized) > COMPRESSION_THRESHOLD:
                serialized = zlib.compress(serialized)
                message.metadata.compression = "zlib"

        # Apply encryption if needed
        if format in [SerializationFormat.ENCRYPTED_JSON, SerializationFormat.ENCRYPTED_MSGPACK]:
            if self.fernet:
                serialized = self.fernet.encrypt(serialized)
                message.metadata.encryption = "fernet"
            else:
                self.logger.warning("Encryption requested but not available")

        # Update metadata
        message.metadata.size_bytes = len(serialized)
        message.metadata.checksum = hashlib.sha256(serialized).hexdigest()

        # Check size limit
        if len(serialized) > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {len(serialized)} bytes")

        return serialized

    def deserialize(self,
                    data: bytes,
                    format: SerializationFormat | None = None) -> ProtocolMessage:
        """Deserialize bytes to message."""
        format = format or self.default_format

        # Decrypt if needed
        if format in [SerializationFormat.ENCRYPTED_JSON, SerializationFormat.ENCRYPTED_MSGPACK]:
            if self.fernet:
                data = self.fernet.decrypt(data)
            else:
                raise ValueError("Cannot decrypt: encryption not available")

        # Decompress if needed
        if format in [SerializationFormat.COMPRESSED_JSON, SerializationFormat.COMPRESSED_MSGPACK]:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                # Not compressed, continue
                pass

        # Deserialize
        if format in [SerializationFormat.JSON, SerializationFormat.COMPRESSED_JSON,
                      SerializationFormat.ENCRYPTED_JSON]:
            message_dict = _json_loads(data)
        elif MSGPACK_AVAILABLE and format in [SerializationFormat.MSGPACK,
                                               SerializationFormat.COMPRESSED_MSGPACK,
                                               SerializationFormat.ENCRYPTED_MSGPACK]:
            message_dict = msgpack.unpackb(data, raw=False)
        else:
            # Try JSON as fallback
            message_dict = _json_loads(data)

        return ProtocolMessage.from_dict(message_dict)

# ==============================================================================
# VERSION MANAGER
# ==============================================================================
class VersionManager:
    """Handles protocol version compatibility and migration."""

    def __init__(self):
        self.current_version = PROTOCOL_VERSION
        self.supported_versions = set(PROTOCOL_VERSIONS)
        self.migration_functions = {
            ("1.0", "1.1"): self._migrate_1_0_to_1_1,
            ("1.1", "2.0"): self._migrate_1_1_to_2_0,
            ("1.0", "2.0"): self._migrate_1_0_to_2_0,
        }

    def is_version_supported(self, version: str) -> bool:
        """Check if version is supported."""
        return version in self.supported_versions

    def migrate_message(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """Migrate message to current version."""
        message_version = message_dict.get("version", "1.0")

        if message_version == self.current_version:
            return message_dict

        if not self.is_version_supported(message_version):
            raise ValueError(f"Unsupported version: {message_version}")

        # Find migration path
        migration_key = (message_version, self.current_version)
        if migration_key in self.migration_functions:
            return self.migration_functions[migration_key](message_dict)

        # Try multi-step migration
        return self._multi_step_migration(message_dict, message_version)

    def _multi_step_migration(self, message_dict: dict[str, Any], from_version: str) -> dict[str, Any]:  # noqa: E501
        """Perform multi-step migration."""
        current = from_version
        result = message_dict.copy()

        # Find path from current to target version
        version_order = ["1.0", "1.1", "2.0"]
        start_idx = version_order.index(current)
        target_idx = version_order.index(self.current_version)

        for i in range(start_idx, target_idx):
            from_ver = version_order[i]
            to_ver = version_order[i + 1]
            migration_key = (from_ver, to_ver)

            if migration_key in self.migration_functions:
                result = self.migration_functions[migration_key](result)

        return result

    def _migrate_1_0_to_1_1(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """Migrate from version 1.0 to 1.1."""
        result = message_dict.copy()
        result["version"] = "1.1"

        # Add priority if missing
        if "priority" not in result:
            result["priority"] = PRIORITY_NORMAL

        return result

    def _migrate_1_1_to_2_0(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """Migrate from version 1.1 to 2.0."""
        result = message_dict.copy()
        result["version"] = "2.0"

        # Add metadata if missing
        if "metadata" not in result:
            result["metadata"] = asdict(MessageMetadata(version="2.0"))

        # Ensure category is valid
        if "category" in result:
            try:
                MessageCategory(result["category"])
            except ValueError:
                result["category"] = MessageCategory.SYSTEM.value

        return result

    def _migrate_1_0_to_2_0(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """Direct migration from 1.0 to 2.0."""
        # First migrate to 1.1
        result = self._migrate_1_0_to_1_1(message_dict)
        # Then to 2.0
        return self._migrate_1_1_to_2_0(result)

# ==============================================================================
# MESSAGE FACTORY
# ==============================================================================
class MessageFactory:
    """Factory for creating validated messages."""

    def __init__(self, validator: SchemaValidator):
        self.validator = validator
        self.logger = logging.getLogger("MessageFactory")

    def create_market_data(self,
                          symbol: str,
                          source: str,
                          bid: float | None = None,
                          ask: float | None = None,
                          last: float | None = None,
                          volume: int | None = None,
                          **kwargs) -> ProtocolMessage:
        """Create validated market data message."""
        data = {
            "symbol": symbol,
            "timestamp": time.time(),
            "bid": bid,
            "ask": ask,
            "last": last,
            "volume": volume,
            "bid_size": kwargs.get("bid_size"),
            "ask_size": kwargs.get("ask_size")
        }

        message = ProtocolMessage(
            category=MessageCategory.MARKET,
            message_type="MARKET_DATA",
            source=source,
            data=data,
            priority=kwargs.get("priority", PRIORITY_HIGH)
        )

        # Validate
        valid, error = self.validator.validate_message(message)
        if not valid:
            raise ValueError(f"Invalid market data: {error}")

        return message

    def create_order(self,
                     symbol: str,
                     action: str,
                     quantity: int,
                     order_type: str,
                     source: str,
                     price: float | None = None,
                     **kwargs) -> ProtocolMessage:
        """Create validated order message."""
        data = {
            "order_id": kwargs.get("order_id", str(uuid.uuid4())),
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "stop_price": kwargs.get("stop_price"),
            "time_in_force": kwargs.get("time_in_force", "DAY")
        }

        message = ProtocolMessage(
            category=MessageCategory.TRADE,
            message_type="TRADE_ORDER",
            source=source,
            data=data,
            priority=kwargs.get("priority", PRIORITY_CRITICAL)
        )

        # Validate
        valid, error = self.validator.validate_message(message)
        if not valid:
            raise ValueError(f"Invalid order: {error}")

        return message

    def create_risk_update(self,
                          source: str,
                          portfolio_delta: float | None = None,
                          portfolio_gamma: float | None = None,
                          portfolio_theta: float | None = None,
                          portfolio_vega: float | None = None,
                          **kwargs) -> ProtocolMessage:
        """Create validated risk update message."""
        data = {
            "timestamp": time.time(),
            "portfolio_delta": portfolio_delta,
            "portfolio_gamma": portfolio_gamma,
            "portfolio_theta": portfolio_theta,
            "portfolio_vega": portfolio_vega,
            "portfolio_value": kwargs.get("portfolio_value"),
            "var_95": kwargs.get("var_95"),
            "max_drawdown": kwargs.get("max_drawdown")
        }

        message = ProtocolMessage(
            category=MessageCategory.RISK,
            message_type="RISK_UPDATE",
            source=source,
            data=data,
            priority=kwargs.get("priority", PRIORITY_HIGH)
        )

        # Validate
        valid, error = self.validator.validate_message(message)
        if not valid:
            raise ValueError(f"Invalid risk update: {error}")

        return message

    def create_alert(self,
                     alert_type: str,
                     message: str,
                     source: str,
                     severity: str = "INFO",
                     **kwargs) -> ProtocolMessage:
        """Create alert message."""
        data = {
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": time.time(),
            "details": kwargs.get("details", {})
        }

        # Set priority based on severity
        priority_map = {
            "CRITICAL": PRIORITY_CRITICAL,
            "ERROR": PRIORITY_HIGH,
            "WARNING": PRIORITY_NORMAL,
            "INFO": PRIORITY_LOW
        }

        message_obj = ProtocolMessage(
            category=MessageCategory.ALERT,
            message_type="ALERT",
            source=source,
            data=data,
            priority=priority_map.get(severity, PRIORITY_NORMAL)
        )

        return message_obj

# ==============================================================================
# PROTOCOL MANAGER
# ==============================================================================
class ProtocolManager:
    """Central manager for protocol operations."""

    def __init__(self,
                 validation_level: ValidationLevel = ValidationLevel.STRICT,
                 default_format: SerializationFormat = SerializationFormat.COMPRESSED_JSON,
                 encryption_key: bytes | None = None):
        self.validation_level = validation_level
        self.validator = SchemaValidator()
        self.serializer = SerializationManager(default_format, encryption_key)
        self.version_manager = VersionManager()
        self.factory = MessageFactory(self.validator)
        self.logger = logging.getLogger("ProtocolManager")

        # Statistics
        self.stats = defaultdict(int)

    def create_message(self,
                      category: str | MessageCategory,
                      message_type: str,
                      source: str,
                      data: dict[str, Any],
                      **kwargs) -> ProtocolMessage:
        """Create a new protocol message."""
        if isinstance(category, str):
            category = MessageCategory(category)

        message = ProtocolMessage(
            category=category,
            message_type=message_type,
            source=source,
            data=data,
            **kwargs
        )

        # Validate if required
        if self.validation_level >= ValidationLevel.STANDARD:
            valid, error = self.validator.validate_message(message)
            if not valid:
                raise ValueError(f"Message validation failed: {error}")

        self.stats["messages_created"] += 1
        return message

    def serialize_message(self,
                         message: ProtocolMessage,
                         format: SerializationFormat | None = None) -> bytes:
        """Serialize a message to bytes."""
        try:
            serialized = self.serializer.serialize(message, format)
            self.stats["messages_serialized"] += 1
            self.stats["bytes_serialized"] += len(serialized)
            return serialized
        except Exception as e:
            self.stats["serialization_errors"] += 1
            self.logger.error("Serialization error: %s", e)
            raise

    def deserialize_message(self,
                           data: bytes,
                           format: SerializationFormat | None = None) -> ProtocolMessage:
        """Deserialize bytes to message."""
        try:
            message = self.serializer.deserialize(data, format)

            # Check version and migrate if needed
            if hasattr(message, 'metadata') and message.metadata.version != PROTOCOL_VERSION:
                message_dict = message.to_dict()
                migrated_dict = self.version_manager.migrate_message(message_dict)
                message = ProtocolMessage.from_dict(migrated_dict)

            # Validate if required
            if self.validation_level >= ValidationLevel.BASIC:
                valid, error = self.validator.validate_message(message)
                if not valid and self.validation_level >= ValidationLevel.STRICT:
                    raise ValueError(f"Message validation failed: {error}")

            self.stats["messages_deserialized"] += 1
            return message
        except Exception as e:
            self.stats["deserialization_errors"] += 1
            self.logger.error("Deserialization error: %s", e)
            raise

    def get_stats(self) -> dict[str, int]:
        """Get protocol statistics."""
        return dict(self.stats)

# ==============================================================================
# SPECIALIZED MESSAGE TYPES
# ==============================================================================
@dataclass
class SystemStatusMessage:
    """System status update message."""
    component: str
    status: str  # HEALTHY, DEGRADED, ERROR, OFFLINE
    cpu_usage: float
    memory_usage: float
    active_connections: int
    uptime_seconds: float
    last_update: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class HeartbeatMessage:
    """Heartbeat message for connection monitoring."""
    source: str
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorMessage:
    """Error notification message."""
    error_code: str
    error_message: str
    source: str
    severity: str  # CRITICAL, ERROR, WARNING
    timestamp: float = field(default_factory=time.time)
    stack_trace: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# EXAMPLE USAGE
@dataclass
class OrderMessage:
    """Normalized equity / option order message crossing the Z-series boundary."""
    order_id: str = ""
    symbol: str = ""
    quantity: int = 0
    side: str = "buy"             # "buy" | "sell" | options sides
    order_type: str = "market"    # "market" | "limit" | "stop" …
    price: float | None = None
    time_in_force: str = "DAY"
    status: str = "pending"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
def example_usage():
    """Demonstrate protocol usage."""
    logging.info("\n" + "="*60)
    logging.info("TRADOV Message Protocol - Enhanced Version")
    logging.info("="*60)

    # Create protocol manager
    manager = ProtocolManager(
        validation_level=ValidationLevel.STRICT,
        default_format=SerializationFormat.COMPRESSED_JSON
    )

    logging.info("\n1. Creating Messages with Validation")
    logging.info("-" * 40)

    try:
        # Create market data message
        market_msg = manager.factory.create_market_data(
            symbol="TRAD",
            source="MarketDataFeed",
            bid=450.25,
            ask=450.30,
            last=450.28,
            volume=1000000,
            bid_size=100,
            ask_size=150
        )
        logging.info("✅ Market data message created: %s", market_msg.message_id)

        # Create order message
        order_msg = manager.factory.create_order(
            symbol="TRAD",
            action="BUY",
            quantity=100,
            order_type="LIMIT",
            price=450.00,
            source="StrategyEngine"
        )
        logging.info("✅ Order message created: %s", order_msg.message_id)

        # Create risk update
        risk_msg = manager.factory.create_risk_update(
            source="RiskEngine",
            portfolio_delta=125.5,
            portfolio_gamma=-10.2,
            portfolio_theta=-156.8,
            portfolio_vega=-523.1,
            portfolio_value=1000000.0
        )
        logging.info("✅ Risk update created: %s", risk_msg.message_id)

    except ValueError as e:
        logging.info("❌ Validation error: %s", e)

    logging.info("\n2. Message Serialization")
    logging.info("-" * 40)

    # Test different formats
    formats = [
        SerializationFormat.JSON,
        SerializationFormat.COMPRESSED_JSON,
    ]

    if MSGPACK_AVAILABLE:
        formats.extend([
            SerializationFormat.MSGPACK,
            SerializationFormat.COMPRESSED_MSGPACK
        ])

    for format in formats:
        serialized = manager.serialize_message(market_msg, format)
        logging.info("   %s: %s bytes", format.value, len(serialized))

    logging.info("\n3. Message Priorities")
    logging.info("-" * 40)

    # Create messages with different priorities
    critical_alert = manager.factory.create_alert(
        alert_type="RISK_BREACH",
        message="Portfolio delta limit exceeded",
        source="RiskMonitor",
        severity="CRITICAL"
    )
    logging.info("   Critical alert priority: %s", critical_alert.priority)

    info_alert = manager.factory.create_alert(
        alert_type="SYSTEM_INFO",
        message="Market data feed connected",
        source="SystemMonitor",
        severity="INFO"
    )
    logging.info("   Info alert priority: %s", info_alert.priority)

    logging.info("\n4. Version Migration")
    logging.info("-" * 40)

    # Simulate old version message
    old_message = {
        "version": "1.0",
        "category": "MARKET",
        "type": "MARKET_DATA",
        "source": "LegacySystem",
        "timestamp": time.time(),
        "data": {"symbol": "TRAD", "last": 450.0}
    }

    migrated = manager.version_manager.migrate_message(old_message)
    logging.info("   Migrated from v%s to v%s", old_message['version'], migrated['version'])
    logging.info("   Added fields: %s", set(migrated.keys()) - set(old_message.keys()))

    logging.info("\n5. Protocol Statistics")
    logging.info("-" * 40)

    stats = manager.get_stats()
    for key, value in stats.items():
        if value > 0:
            logging.info("   %s: %s", key, value)

    logging.info("\n✅ Enhanced Protocol Features:")
    logging.info("   • Strict JSON Schema validation")
    logging.info("   • Multiple serialization formats")
    logging.info("   • Message compression for large payloads")
    logging.info("   • Priority-based message handling")
    logging.info("   • Protocol version control and migration")
    logging.info("   • Comprehensive error handling")
    logging.info("   • Performance statistics")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    example_usage()
