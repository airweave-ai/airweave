"""Billing module for Airweave.

This module provides a clean, modular billing system with:
- Pure business logic separated from infrastructure
- Clean repository pattern for database operations
- Simplified webhook processing
- Clear API endpoints

Usage:
    from airweave.platform.billing import billing_service

    # For direct service usage
    subscription = await billing_service.get_subscription_info(db, org_id)
"""

from airweave.billing.service import billing_service

__all__ = [
    "billing_service",
]
