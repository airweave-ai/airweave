"""Backfill key_prefix and key_hash for existing API keys.

Run post-deploy to populate the key_prefix and key_hash columns for keys
created before the CASA-28 migration. Requires ENCRYPTION_KEY to be set in
the environment (not safe to run inside Alembic migrations where it may
be absent).

Usage:
    poetry run python -m airweave.scripts.backfill_key_prefix
"""

import asyncio
import hashlib

from cryptography.fernet import InvalidToken
from sqlalchemy import or_, select, update

from airweave.core import credentials
from airweave.core.logging import logger
from airweave.db.session import get_db_context
from airweave.models.api_key import APIKey


async def backfill() -> None:
    """Decrypt each key and populate key_prefix/key_hash where NULL."""
    async with get_db_context() as db:
        query = select(APIKey).where(
            or_(APIKey.key_prefix.is_(None), APIKey.key_hash.is_(None))
        )
        result = await db.execute(query)
        keys = result.scalars().all()

        if not keys:
            logger.info("No keys need backfilling")
            return

        logger.info(f"Backfilling key_prefix/key_hash for {len(keys)} keys")
        updated = 0

        for api_key in keys:
            try:
                decrypted_data = credentials.decrypt(api_key.encrypted_key)
                plain_key = decrypted_data.get("key") if isinstance(decrypted_data, dict) else None
                if not plain_key:
                    logger.warning(f"Key {api_key.id}: could not extract plaintext key")
                    continue

                values = {}
                if api_key.key_prefix is None:
                    values["key_prefix"] = plain_key[:8]
                if api_key.key_hash is None:
                    values["key_hash"] = hashlib.sha256(plain_key.encode()).hexdigest()

                if values:
                    stmt = (
                        update(APIKey)
                        .where(APIKey.id == api_key.id)
                        .values(**values)
                    )
                    await db.execute(stmt)
                    updated += 1
            except (InvalidToken, ValueError) as e:
                logger.error(f"Key {api_key.id}: decryption failed: {e}")

        await db.commit()
        logger.info(f"Backfill complete: {updated}/{len(keys)} keys updated")


if __name__ == "__main__":
    asyncio.run(backfill())
