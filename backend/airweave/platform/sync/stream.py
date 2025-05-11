"""Module for async data streaming with backpressure."""

import asyncio
import logging
from typing import AsyncGenerator, Generic, Optional, TypeVar

from airweave.platform.entities._base import BaseEntity

T = TypeVar("T", bound=BaseEntity)


class AsyncSourceStream(Generic[T]):
    """Manages asynchronous processing of entity streams with separate producer/consumer loops.

    - Producer: generates entities from a source
    - Consumer: processes entities independently

    Uses async queue to buffer entities and implement backpressure.
    """

    def __init__(
        self,
        source_generator: AsyncGenerator[T, None],
        queue_size: int = 100,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the async source stream.

        Args:
            source_generator: The source async generator
            queue_size: Size of the queue connecting producer and consumer
            logger: Optional contextualized logger, falls back to global logger if not provided
        """
        self.source_generator = source_generator
        # Queue is used to buffer entities and implement backpressure
        self.queue: asyncio.Queue[Optional[T]] = asyncio.Queue(maxsize=queue_size)
        self.producer_task = None
        self.is_running = True
        self.producer_done = asyncio.Event()
        self.producer_exception = None
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger

    async def __aenter__(self):
        """Context manager entry point."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point."""
        await self.stop()
        # Don't suppress exceptions
        return False

    async def _producer(self):
        """Producer task that fills the queue from the source generator."""
        try:
            async for item in self.source_generator:
                if not self.is_running:
                    self.logger.info("Producer stopping early")
                    break

                # Put item in queue, waiting if queue is full.
                # This is a blocking call, so consumer will wait until the queue has space
                # Effectively, this is a backpressure mechanism.
                await self.queue.put(item)

            self.logger.info("Source generator exhausted")
        except Exception as e:
            self.logger.error(f"Error in producer: {e}")
            self.producer_exception = e
            # Re-raise to ensure proper error handling -> THIS DOES NOT WORK
            raise
        finally:
            # Signal we're done by putting None in the queue and setting the done event
            await self.queue.put(None)
            self.producer_done.set()

    async def start(self):
        """Start the background producer task.

        Runs the producer in a separate task so that it can run independently of the consumer.
        """
        self.producer_task = asyncio.create_task(self._producer())

    async def stop(self):
        """Stop the producer and clean up resources."""
        self.is_running = False
        if self.producer_task:
            # Give producer a chance to finish gracefully
            try:
                await asyncio.wait_for(self.producer_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("Producer task did not complete in time, cancelling")
                self.producer_task.cancel()
                try:
                    await self.producer_task
                except asyncio.CancelledError:
                    pass

    async def get_entities(self) -> AsyncGenerator[T, None]:
        """Get entities one at a time from the queue.

        Yields entities as they become available, allowing consumer to process
        at its own pace.
        """
        if not self.producer_task:
            await self.start()

        while True:
            # Get next item from queue, if available
            item = await self.queue.get()
            self.queue.task_done()

            # None is our sentinel value for end of stream
            if item is None:
                # Check if the producer failed before yielding any items
                if self.producer_exception:
                    self.logger.error("Producer failed with error before yielding any items")
                    raise self.producer_exception
                break

            yield item

            # Check if producer had an error after yielding the item
            if self.producer_exception:
                self.logger.error("Producer encountered an error, stopping consumer")
                raise self.producer_exception
