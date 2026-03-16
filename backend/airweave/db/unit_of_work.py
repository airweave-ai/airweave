"""Unit of work for database transactions."""

from types import TracebackType
from typing import Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Unit of work for database transactions.

    Usage:
    -----
    ```python
    await crud.create(db, obj_in=obj_in)  # commits automatically

    async with UnitOfWork(session) as uow:
        db_obj = await crud.create(db, obj_in=obj_in, uow=uow)
        # ... do something with db_obj ...
        db_obj.some_attribute = "some_value"
        await crud.create(db, obj_in=other_obj_in, uow=uow)

    # The transaction is committed or rolled back as soon as the context manager exits.
    ```

    """

    def __init__(self, session: AsyncSession):
        """Initialize the UnitOfWork with a database session.

        Args:
        ----
            session (AsyncSession): The database session.

        """
        self.session = session
        self._committed = False
        self._rolledback = False

    @property
    def committed(self) -> bool:
        """Check if the transaction has been committed.

        Returns:
        -------
            bool: True if the transaction has been committed, False otherwise.

        """
        return self._committed

    async def commit(self) -> None:
        """Commit the transaction.

        If the transaction has already been committed or rolled back, this method does nothing.
        """
        if not self._committed and not self._rolledback:
            await self.session.commit()
            self._committed = True

    async def rollback(self) -> None:
        """Rollback the transaction.

        If the transaction has already been committed or rolled back, this method does nothing.
        """
        if not self._committed and not self._rolledback:
            await self.session.rollback()
            self._rolledback = True

    async def __aenter__(self) -> "UnitOfWork":
        """Enter the context manager.

        Returns:
        -------
            UnitOfWork: The UnitOfWork instance.

        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager.

        Args:
        ----
            exc_type (Type[Exception]): The exception type.
            exc_val (Exception): The exception value.
            exc_tb (TracebackType): The exception traceback.

        """
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
