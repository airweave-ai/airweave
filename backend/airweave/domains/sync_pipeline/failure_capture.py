"""Failure artifact capture for sync replay/debugging.

The capture layer stores small, redacted JSON artifacts for failures that are
otherwise hard to reproduce from logs alone. It is intentionally storage-backed
and side-effect-light so callers can use it best-effort without changing normal
sync semantics.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping, Optional

from airweave.domains.storage.paths import StoragePaths
from airweave.domains.storage.protocols import StorageBackend

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.contexts import SyncContext
    from airweave.platform.entities._base import BaseEntity


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENSITIVE_KEYWORDS = (
    "access_token",
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)


@dataclass(frozen=True)
class FailureCaptureLimits:
    """Limits applied to failure artifacts to avoid large/sensitive dumps."""

    max_string_chars: int = 1_000
    max_list_items: int = 20
    max_dict_items: int = 40


class SyncFailureCapture:
    """Stores redacted sync failure artifacts in the raw sync storage tree."""

    def __init__(
        self,
        storage: StorageBackend,
        limits: Optional[FailureCaptureLimits] = None,
    ) -> None:
        """Initialize with a storage backend."""
        self._storage = storage
        self._limits = limits or FailureCaptureLimits()

    async def capture_entity_failure(
        self,
        *,
        entity: "BaseEntity",
        stage: str,
        error: Exception,
        sync_context: "SyncContext",
        include_snapshot: bool = True,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Capture an entity-scoped failure and return the artifact path."""
        artifact = self._base_artifact(stage=stage, error=error, sync_context=sync_context)
        artifact["entity"] = (
            self._entity_snapshot(entity) if include_snapshot else self._entity_ref(entity)
        )
        if extra:
            artifact["extra"] = self._redact(extra)

        return await self._write_artifact(
            artifact=artifact,
            stage=stage,
            sync_context=sync_context,
            artifact_id=str(getattr(entity, "entity_id", "unknown")),
        )

    async def capture_batch_failure(
        self,
        *,
        entities: list["BaseEntity"],
        stage: str,
        error: Exception,
        sync_context: "SyncContext",
        extra: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Capture a batch-scoped failure and return the artifact path."""
        artifact = self._base_artifact(stage=stage, error=error, sync_context=sync_context)
        entity_refs = [
            self._entity_ref(entity) for entity in entities[: self._limits.max_list_items]
        ]
        artifact["batch"] = {
            "entity_count": len(entities),
            "entities": entity_refs,
            "truncated": len(entities) > self._limits.max_list_items,
        }
        if extra:
            artifact["extra"] = self._redact(extra)

        raw_id = "|".join(str(getattr(entity, "entity_id", "")) for entity in entities)
        digest = hashlib.sha256(raw_id.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return await self._write_artifact(
            artifact=artifact,
            stage=stage,
            sync_context=sync_context,
            artifact_id=f"batch-{digest}",
        )

    def _base_artifact(
        self,
        *,
        stage: str,
        error: Exception,
        sync_context: "SyncContext",
    ) -> dict[str, Any]:
        """Build the shared artifact envelope."""
        return {
            "version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "sync": {
                "sync_id": str(sync_context.sync.id),
                "sync_job_id": str(sync_context.sync_job.id),
                "collection_id": str(sync_context.collection.id),
                "source_connection_id": str(sync_context.source_connection_id),
                "source_type": sync_context.source_short_name,
                "organization_id": str(sync_context.organization_id),
            },
            "error": {
                "type": type(error).__name__,
                "message": self._clean_string(str(error) or "(empty error message)"),
            },
        }

    async def _write_artifact(
        self,
        *,
        artifact: dict[str, Any],
        stage: str,
        sync_context: "SyncContext",
        artifact_id: str,
    ) -> str:
        """Persist an artifact under the sync's raw storage tree."""
        path = StoragePaths.sync_failure_artifact_path(
            sync_id=sync_context.sync.id,
            sync_job_id=sync_context.sync_job.id,
            stage=stage,
            artifact_id=artifact_id,
        )
        await self._storage.write_json(path, artifact)
        return path

    def _entity_snapshot(self, entity: "BaseEntity") -> dict[str, Any]:
        """Return a redacted entity snapshot useful for replay/debugging."""
        snapshot = self._entity_ref(entity)
        textual_representation = getattr(entity, "textual_representation", None)
        if textual_representation is not None:
            snapshot["textual_representation"] = {
                "chars": len(textual_representation),
                "preview": self._clean_string(textual_representation),
            }

        if hasattr(entity, "model_dump"):
            raw = entity.model_dump(mode="json", exclude={"airweave_system_metadata"})
            snapshot["fields"] = self._redact(raw)
        return snapshot

    def _entity_ref(self, entity: "BaseEntity") -> dict[str, Any]:
        """Return stable identifying fields for an entity."""
        metadata = getattr(entity, "airweave_system_metadata", None)
        return {
            "entity_id": str(getattr(entity, "entity_id", "")),
            "entity_type": entity.__class__.__name__,
            "original_entity_id": str(getattr(metadata, "original_entity_id", "") or ""),
            "chunk_index": getattr(metadata, "chunk_index", None),
        }

    def _redact(self, value: Any) -> Any:
        """Recursively redact sensitive values and trim large structures."""
        if isinstance(value, Mapping):
            redacted: dict[str, Any] = {}
            items = list(value.items())
            for key, item_value in items[: self._limits.max_dict_items]:
                key_str = str(key)
                if self._is_sensitive_key(key_str):
                    redacted[key_str] = "[REDACTED]"
                else:
                    redacted[key_str] = self._redact(item_value)
            if len(items) > self._limits.max_dict_items:
                redacted["_truncated_keys"] = len(items) - self._limits.max_dict_items
            return redacted

        if isinstance(value, list):
            redacted_items = [self._redact(item) for item in value[: self._limits.max_list_items]]
            if len(value) > self._limits.max_list_items:
                truncated_items = len(value) - self._limits.max_list_items
                redacted_items.append({"_truncated_items": truncated_items})
            return redacted_items

        if isinstance(value, tuple):
            return self._redact(list(value))

        if isinstance(value, str):
            return self._clean_string(value)

        return value

    def _clean_string(self, value: str) -> str:
        """Remove control characters and trim long strings."""
        clean = _CONTROL_CHARS_RE.sub(r"\\uFFFD", value)
        if len(clean) > self._limits.max_string_chars:
            truncated_chars = len(clean) - self._limits.max_string_chars
            return (
                f"{clean[: self._limits.max_string_chars]}"
                f"...[truncated {truncated_chars} chars]"
            )
        return clean

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """Return true if a field name looks credential-bearing."""
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in _SENSITIVE_KEYWORDS)
