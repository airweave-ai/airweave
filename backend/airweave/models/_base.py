"""Base models for the application."""

import uuid

from sqlalchemy import UUID, Column, DateTime, ForeignKey, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

from airweave.core.datetime_utils import utc_now_naive


class Base(DeclarativeBase):
    """Base class for all models."""

    id = Column(UUID, primary_key=True, default=uuid.uuid4, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    modified_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


class OrganizationBase(Base):
    """Base class for organization-related tables."""

    __abstract__ = True

    @declared_attr
    def organization_id(cls):
        """Organization ID column with index for efficient org-scoped queries."""
        return Column(
            UUID,
            ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
            index=True,  # Index by default for all org-scoped tables
        )


class UserMixin:
    """Mixin for adding nullable user tracking to a model."""

    @declared_attr
    def created_by_email(cls):
        return Column(String, nullable=True)  # Made nullable for API key support

    @declared_attr
    def modified_by_email(cls):
        return Column(String, nullable=True)  # Made nullable for API key support
