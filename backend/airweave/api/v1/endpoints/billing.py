"""API endpoints for billing operations.

This module provides the HTTP interface for billing operations,
delegating all business logic to the billing service.
"""

from typing import Optional

from fastapi import Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.billing.service import billing_service
from airweave.billing.webhook_handler import BillingWebhookProcessor
from airweave.core.config import settings
from airweave.core.exceptions import ExternalServiceError
from airweave.integrations.stripe_client import stripe_client

router = TrailingSlashRouter()


@router.post("/checkout-session", response_model=schemas.CheckoutSessionResponse)
async def create_checkout_session(
    request: schemas.CheckoutSessionRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.CheckoutSessionResponse:
    """Create a Stripe checkout session for subscription.

    Initiates the Stripe checkout flow for subscribing to a plan.

    Args:
        request: Checkout session request with plan and URLs
        db: Database session
        ctx: Authentication context

    Returns:
        Checkout session URL to redirect user to

    Raises:
        HTTPException: If billing is disabled or request is invalid
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    checkout_url = await billing_service.start_subscription_checkout(
        db=db,
        plan=request.plan,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        ctx=ctx,
    )

    return schemas.CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/yearly/checkout-session", response_model=schemas.CheckoutSessionResponse)
async def create_yearly_prepay_checkout_session(
    request: schemas.CheckoutSessionRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.CheckoutSessionResponse:
    """Create a Stripe checkout session for yearly prepay (no existing subscription).

    This creates a one-time payment for a full year at 20% discount, and records
    the prepay intent. After payment (via webhook), we will credit balance,
    create the monthly subscription and apply a 20% coupon.
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    checkout_url = await billing_service.start_yearly_prepay_checkout(
        db=db,
        plan=request.plan,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        ctx=ctx,
    )

    return schemas.CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/portal-session", response_model=schemas.CustomerPortalResponse)
async def create_portal_session(
    request: schemas.CustomerPortalRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.CustomerPortalResponse:
    """Create a Stripe customer portal session.

    The customer portal allows users to:
    - Update payment methods
    - Download invoices
    - Cancel subscription
    - Update billing address

    Args:
        request: Portal session request with return URL
        db: Database session
        ctx: Authentication context

    Returns:
        Portal session URL to redirect user to

    Raises:
        HTTPException: If billing is disabled or no billing record exists
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    portal_url = await billing_service.create_customer_portal_session(
        db=db,
        ctx=ctx,
        return_url=request.return_url,
    )

    return schemas.CustomerPortalResponse(portal_url=portal_url)


@router.get("/subscription", response_model=schemas.SubscriptionInfo)
async def get_subscription(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SubscriptionInfo:
    """Get current subscription information.

    Returns comprehensive subscription details including:
    - Current plan and status
    - Usage limits
    - Billing period

    Args:
        db: Database session
        ctx: Authentication context

    Returns:
        Subscription information
    """
    return await billing_service.get_subscription_info(db, ctx.organization.id)


@router.post("/update-plan", response_model=schemas.MessageResponse)
async def update_subscription_plan(
    request: schemas.UpdatePlanRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.MessageResponse:
    """Update subscription to a different plan.

    Upgrades take effect immediately with proration.
    Downgrades take effect at the end of the current billing period.

    Args:
        request: Plan update request
        db: Database session
        ctx: Authentication context

    Returns:
        Success message

    Raises:
        HTTPException: If update fails or payment method required
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    message = await billing_service.update_subscription_plan(
        db=db,
        ctx=ctx,
        new_plan=request.plan,
        period=(request.period or "monthly"),
    )

    return schemas.MessageResponse(message=message)


@router.post("/cancel", response_model=schemas.MessageResponse)
async def cancel_subscription(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.MessageResponse:
    """Cancel the current subscription.

    The subscription will be canceled at the end of the current billing period,
    allowing continued access until then.

    Args:
        db: Database session
        ctx: Authentication context

    Returns:
        Success message

    Raises:
        HTTPException: If no active subscription or cancellation fails
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    message = await billing_service.cancel_subscription(db, ctx)

    return schemas.MessageResponse(message=message)


@router.post("/reactivate", response_model=schemas.MessageResponse)
async def reactivate_subscription(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.MessageResponse:
    """Reactivate a subscription that's set to cancel.

    This endpoint can only be used if the subscription is set to cancel
    at the end of the current period.

    Args:
        db: Database session
        ctx: Authentication context

    Returns:
        Success message

    Raises:
        HTTPException: If subscription is not set to cancel
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    message = await billing_service.reactivate_subscription(db, ctx)

    return schemas.MessageResponse(message=message)


@router.post("/cancel-plan-change", response_model=schemas.MessageResponse)
async def cancel_pending_plan_change(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.MessageResponse:
    """Cancel a scheduled plan change (downgrade).

    Args:
        db: Database session
        ctx: Authentication context

    Returns:
        Success message

    Raises:
        HTTPException: If no pending plan change
    """
    if not settings.STRIPE_ENABLED:
        raise ExternalServiceError(
            service_name="Billing",
            message="Billing is not enabled for this instance",
        )

    message = await billing_service.cancel_pending_plan_change(db, ctx)

    return schemas.MessageResponse(message=message)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(deps.get_db),
) -> Response:
    """Handle Stripe webhook events.

    This endpoint receives and processes Stripe webhook events for:
    - Subscription lifecycle (created, updated, deleted)
    - Payment events (succeeded, failed)
    - Customer events

    Security:
    - Verifies webhook signature
    - Idempotent processing
    - Comprehensive error handling

    Args:
        request: Raw HTTP request
        stripe_signature: Stripe signature header
        db: Database session

    Returns:
        200 OK on success, 400 on error
    """
    if not settings.STRIPE_ENABLED:
        return Response(status_code=200)

    # Get raw body
    try:
        payload = await request.body()
    except Exception:
        return Response(status_code=400)

    # Verify signature
    if not stripe_signature:
        return Response(status_code=400)

    if not stripe_client:
        return Response(status_code=500)

    try:
        event = stripe_client.verify_webhook_signature(payload, stripe_signature)
    except ValueError:
        return Response(status_code=400)

    # Process event
    try:
        processor = BillingWebhookProcessor(db)
        await processor.process_event(event)
        return Response(status_code=200)
    except Exception:
        return Response(status_code=500)
