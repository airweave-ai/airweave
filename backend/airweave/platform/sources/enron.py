"""Enron Email source — syncs the CMU Enron maildir corpus into Airweave.

Modeled after the Gmail connector: emails extend EmailEntity, the body is
saved as a plain-text file (processed by the standard conversion pipeline),
and entity fields carry searchable metadata.

Expects the standard CMU corpus layout (or a pre-filtered subset built by
``evals/scripts/build_enron_subset.py``):
    {maildir_path}/
    ├── allen-p/
    │   ├── inbox/
    │   │   ├── 1.
    │   │   ├── 2.
    │   │   └── ...
    │   ├── sent_items/
    │   └── ...
    ├── bass-e/
    └── ...
"""

import email
import email.policy
import email.utils
import os
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

from airweave.platform.configs.auth import EnronAuthConfig
from airweave.platform.configs.config import EnronConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.enron import EnronEmailEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage import FileSkippedException
from airweave.platform.utils.filename_utils import safe_filename
from airweave.schemas.source_connection import AuthenticationMethod

_CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SNIPPET_LENGTH = 200


@source(
    name="Enron Email Corpus",
    short_name="enron",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=EnronAuthConfig,
    config_class=EnronConfig,
    labels=["Benchmark", "Email"],
    internal=True,
)
class EnronSource(BaseSource):
    """Source that reads the CMU Enron maildir corpus and yields EnronEmailEntity.

    Like the Gmail connector, the email body is saved as a file and entity
    fields carry structured metadata for search and filtering.
    """

    def __init__(self):
        """Initialize the Enron source."""
        super().__init__()
        self.maildir_path: str = ""

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], EnronAuthConfig]] = None,
        config: Optional[Union[Dict[str, Any], EnronConfig]] = None,
    ) -> "EnronSource":
        """Create a new Enron source instance."""
        instance = cls()
        if config:
            if isinstance(config, dict):
                instance.maildir_path = config.get("maildir_path", "")
            else:
                instance.maildir_path = config.maildir_path
        return instance

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse an RFC 2822 date string into a timezone-aware datetime."""
        if not date_str:
            return None
        try:
            parsed = email.utils.parsedate_to_datetime(date_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    @staticmethod
    def _sanitize(value: str) -> str:
        """Strip control characters that Vespa/XML-based stores reject."""
        return _CTRL_CHAR_RE.sub("", value)

    @staticmethod
    def _parse_address_list(header_value: Optional[str]) -> List[str]:
        """Split a comma-separated address header into a trimmed list."""
        if not header_value:
            return []
        return [
            _CTRL_CHAR_RE.sub("", addr.strip()) for addr in header_value.split(",") if addr.strip()
        ]

    def _parse_email_file(self, filepath: str) -> Optional[email.message.Message]:
        """Read and parse a single email file, returning None on failure."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return email.message_from_file(f, policy=email.policy.default)
        except Exception as exc:
            self.logger.debug(f"Skipping unreadable file {filepath}: {exc}")
            return None

    def _msg_to_entity_data(
        self, msg: email.message.Message, folder: str, user_dir: str
    ) -> Optional[Tuple[EnronEmailEntity, str]]:
        """Build an EnronEmailEntity + body text from a parsed message.

        Returns None if the message has no Message-ID (unparsable).
        The body is returned separately because it gets saved as a file,
        not stored on the entity.
        """
        message_id = msg.get("Message-ID", "").strip()
        if not message_id:
            return None

        subject = self._sanitize(str(msg.get("Subject", "(no subject)")))
        sender = self._sanitize(str(msg.get("From", "")))
        sender_name = self._sanitize(str(msg.get("X-From", ""))) or None
        to = self._parse_address_list(msg.get("To"))
        cc = self._parse_address_list(msg.get("Cc"))
        sent_at = self._parse_date(msg.get("Date"))

        body_part = msg.get_body(preferencelist=("plain",))
        body_text = body_part.get_content() if body_part else ""

        snippet = self._sanitize(body_text[:SNIPPET_LENGTH].strip()) if body_text else None

        folder_name = folder.split("/", 1)[1] if "/" in folder else folder

        entity = EnronEmailEntity(
            message_id=message_id,
            subject=subject,
            sent_at=sent_at,
            sender=sender,
            sender_name=sender_name,
            to=to,
            cc=cc,
            snippet=snippet,
            folder=folder,
            # FileEntity required fields
            url=f"enron://maildir/{folder}/{message_id}",
            size=len(body_text.encode("utf-8")),
            file_type="text",
            mime_type="text/plain",
            local_path=None,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=user_dir,
                    name=user_dir,
                    entity_type="EnronMailbox",
                ),
                Breadcrumb(
                    entity_id=folder,
                    name=folder_name,
                    entity_type="EnronFolder",
                ),
            ],
        )
        return entity, body_text

    async def _save_body(self, entity: EnronEmailEntity, body_text: str) -> bool:
        """Save the email body as a plain-text file via the file downloader.

        Returns True on success, False if skipped/failed.
        """
        if not body_text:
            return False

        filename = safe_filename(entity.subject, ".txt")
        try:
            await self.file_downloader.save_bytes(
                entity=entity,
                content=body_text.encode("utf-8"),
                filename_with_extension=filename,
                logger=self.logger,
            )
            return True
        except FileSkippedException as exc:
            self.logger.debug(f"Skipping body for {entity.message_id}: {exc.reason}")
            return False
        except Exception as exc:
            self.logger.warning(f"Failed to save body for {entity.message_id}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Entity generation
    # ------------------------------------------------------------------

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Walk the maildir tree and yield EnronEmailEntity instances."""
        self.logger.info(f"Walking maildir: {self.maildir_path}")
        total = 0
        skipped = 0

        for user_dir in sorted(os.listdir(self.maildir_path)):
            user_path = os.path.join(self.maildir_path, user_dir)
            if not os.path.isdir(user_path):
                continue

            for dirpath, _dirnames, filenames in os.walk(user_path):
                folder = os.path.relpath(dirpath, self.maildir_path)

                for fname in filenames:
                    if fname.startswith("."):
                        continue

                    filepath = os.path.join(dirpath, fname)
                    msg = self._parse_email_file(filepath)
                    if msg is None:
                        skipped += 1
                        continue

                    result = self._msg_to_entity_data(msg, folder, user_dir)
                    if result is None:
                        skipped += 1
                        continue

                    entity, body_text = result
                    saved = await self._save_body(entity, body_text)
                    if not saved:
                        continue

                    yield entity
                    total += 1
                    if total % 10_000 == 0:
                        self.logger.info(f"Processed {total:,} emails so far …")

        self.logger.info(f"Complete: {total:,} emails yielded, {skipped:,} skipped")

    async def validate(self) -> bool:
        """Validate that the maildir path exists and looks like the Enron corpus."""
        if not self.maildir_path or not os.path.isdir(self.maildir_path):
            return False
        subdirs = [
            d
            for d in os.listdir(self.maildir_path)
            if os.path.isdir(os.path.join(self.maildir_path, d))
        ]
        return len(subdirs) > 0
