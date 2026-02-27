"""VectorDbDeploymentMetadata model.

Locks the embedding model and dimensions for the entire deployment.
There is always exactly one row — created at first startup and never changed.
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import Base


class VectorDbDeploymentMetadata(Base):
    """Deployment-wide embedding configuration.

    NOT org-scoped: every collection in every org shares
    the same dense/sparse embedder and vector dimensions.

    Exactly one row exists — enforced by the ``singleton`` column
    with a CHECK constraint and UNIQUE index.
    """

    __tablename__ = "vector_db_deployment_metadata"

    singleton: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, unique=True)

    dense_embedder: Mapped[str] = mapped_column(String, nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    sparse_embedder: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        {"comment": "Singleton table — exactly one row, enforced by CHECK(singleton)"},
    )
