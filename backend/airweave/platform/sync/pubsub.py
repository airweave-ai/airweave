"""Pubsub for sync jobs."""

import asyncio
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SyncProgressUpdate(BaseModel):
    """Sync progress update data structure.

    This is sent over the pubsub channel to subscribers
    """

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0
    skipped: int = 0
    is_complete: bool = False  # Add completion flag
    is_failed: bool = False  # Add failure flag


class SyncJobTopic:
    """Represents an active sync job's message stream."""

    def __init__(self, job_id: UUID):
        """Initialize topic."""
        self.job_id = job_id
        self.queues: list[asyncio.Queue] = []
        self.latest_update: Optional[SyncProgressUpdate] = None

    async def publish(self, update: SyncProgressUpdate) -> None:
        """Publish an update to all subscribers."""
        self.latest_update = update
        for queue in self.queues:
            await queue.put(update)

    async def add_subscriber(self) -> asyncio.Queue:
        """Add a new subscriber and send them the latest update if available."""
        queue = asyncio.Queue()
        self.queues.append(queue)
        if self.latest_update:
            await queue.put(self.latest_update)
        return queue

    def remove_subscriber(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber."""
        if queue in self.queues:
            self.queues.remove(queue)


class SyncPubSub:
    """Manages sync job topics and their subscribers."""

    def __init__(self) -> None:
        """Initialize the SyncPubSub instance."""
        self.topics: dict[UUID, SyncJobTopic] = {}

    def get_or_create_topic(self, job_id: UUID) -> SyncJobTopic:
        """Get an existing topic or create a new one."""
        if job_id not in self.topics:
            self.topics[job_id] = SyncJobTopic(job_id)
        return self.topics[job_id]

    def remove_topic(self, job_id: UUID) -> None:
        """Remove a topic when sync is complete."""
        if job_id in self.topics:
            del self.topics[job_id]

    async def publish(self, job_id: UUID, update: SyncProgressUpdate) -> None:
        """Publish an update to a specific job topic."""
        topic = self.get_or_create_topic(job_id)
        await topic.publish(update)
        # If the update indicates completion or failure, schedule topic removal
        if update.is_complete or update.is_failed:
            self.remove_topic(job_id)

    async def subscribe(self, job_id: UUID) -> asyncio.Queue:
        """Subscribe to a job's updates, creating the topic if it doesn't exist."""
        topic = self.get_or_create_topic(job_id)
        return await topic.add_subscriber()

    def unsubscribe(self, job_id: UUID, queue: asyncio.Queue) -> None:
        """Remove a subscriber from a topic."""
        if job_id in self.topics:
            self.topics[job_id].remove_subscriber(queue)


PUBLISH_THRESHOLD = 5


class SyncProgress:
    """Tracks sync progress and automatically publishes updates."""

    def __init__(self, job_id: UUID):
        """Initialize the SyncProgress instance."""
        self.job_id = job_id
        self.stats = SyncProgressUpdate()
        self._last_published = 0
        self._publish_threshold = PUBLISH_THRESHOLD

    def __getattr__(self, name: str) -> int:
        """Get counter value for any stat."""
        return getattr(self.stats, name)

    async def increment(self, stat_name: str, amount: int = 1) -> None:
        """Increment a counter and trigger update if threshold reached."""
        current_value = getattr(self.stats, stat_name, 0)
        setattr(self.stats, stat_name, current_value + amount)

        total_ops = sum(
            [self.stats.inserted, self.stats.updated, self.stats.deleted, self.stats.kept]
        )

        if total_ops - self._last_published >= self._publish_threshold:
            await self._publish()
            self._last_published = total_ops

    async def _publish(self) -> None:
        """Publish current progress."""
        await sync_pubsub.publish(self.job_id, self.stats)

    async def finalize(self, is_complete: bool = True) -> None:
        """Publish final progress."""
        self.stats.is_complete = is_complete
        self.stats.is_failed = not is_complete
        await self._publish()

    def to_dict(self) -> dict:
        """Convert progress to a dictionary."""
        return self.stats.model_dump()


# Create a global instance for the entire app
sync_pubsub = SyncPubSub()
