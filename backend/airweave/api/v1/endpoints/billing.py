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
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.domains.billing.protocols import BillingServiceProtocol, BillingWebhookProtocol

router = TrailingSlashRouter()


@router.post("/checkout-session", response_model=schemas.CheckoutSessionResponse)
async def create_checkout_session(
    request: schemas.CheckoutSessionRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.CheckoutSessionResponse:
    """Create a Stripe checkout session for subscription.

    Initiates the Stripe checkout flow for subscribing to a plan.

    Args:
        request: Checkout session request with plan and URLs
        db: Database session
        ctx: Authentication context
        billing: Billing service

    Returns:
        Checkout session URL to redirect user to
    """
    checkout_url = await billing.start_subscription_checkout(
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
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.CheckoutSessionResponse:
    """Create a Stripe checkout session for yearly prepay (no existing subscription).

    This creates a one-time payment for a full year at 20% discount, and records
    the prepay intent. After payment (via webhook), we will credit balance,
    create the monthly subscription and apply a 20% coupon.
    """
    checkout_url = await billing.start_yearly_prepay_checkout(
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
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
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
        billing: Billing service

    Returns:
        Portal session URL to redirect user to
    """
    portal_url = await billing.create_customer_portal_session(
        db=db,
        ctx=ctx,
        return_url=request.return_url,
    )

    return schemas.CustomerPortalResponse(portal_url=portal_url)


@router.get("/subscription", response_model=schemas.SubscriptionInfo)
async def get_subscription(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.SubscriptionInfo:
    """Get current subscription information.

    Returns comprehensive subscription details including:
    - Current plan and status
    - Usage limits
    - Billing period

    Args:
        db: Database session
        ctx: Authentication context
        billing: Billing service

    Returns:
        Subscription information
    """
    return await billing.get_subscription_info(db, ctx)


@router.post("/update-plan", response_model=schemas.MessageResponse)
async def update_subscription_plan(
    request: schemas.UpdatePlanRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.MessageResponse:
    """Update subscription to a different plan.

    Upgrades take effect immediately with proration.
    Downgrades take effect at the end of the current billing period.

    Args:
        request: Plan update request
        db: Database session
        ctx: Authentication context
        billing: Billing service

    Returns:
        Success message
    """
    message = await billing.update_subscription_plan(
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
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.MessageResponse:
    """Cancel the current subscription.

    The subscription will be canceled at the end of the current billing period,
    allowing continued access until then.

    Args:
        db: Database session
        ctx: Authentication context
        billing: Billing service

    Returns:
        Success message
    """
    message = await billing.cancel_subscription(db, ctx)

    return schemas.MessageResponse(message=message)


@router.post("/reactivate", response_model=schemas.MessageResponse)
async def reactivate_subscription(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.MessageResponse:
    """Reactivate a subscription that's set to cancel.

    This endpoint can only be used if the subscription is set to cancel
    at the end of the current period.

    Args:
        db: Database session
        ctx: Authentication context
        billing: Billing service

    Returns:
        Success message
    """
    message = await billing.reactivate_subscription(db, ctx)

    return schemas.MessageResponse(message=message)


@router.post("/cancel-plan-change", response_model=schemas.MessageResponse)
async def cancel_pending_plan_change(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    billing: BillingServiceProtocol = Inject(BillingServiceProtocol),
) -> schemas.MessageResponse:
    """Cancel a scheduled plan change (downgrade).

    Args:
        db: Database session
        ctx: Authentication context
        billing: Billing service

    Returns:
        Success message
    """
    message = await billing.cancel_pending_plan_change(db, ctx)

    return schemas.MessageResponse(message=message)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(deps.get_db),
    webhook: BillingWebhookProtocol = Inject(BillingWebhookProtocol),
) -> Response:
    """Handle Stripe webhook events.

    This endpoint receives and processes Stripe webhook events for:
    - Subscription lifecycle (created, updated, deleted)
    - Payment events (succeeded, failed)
    - Customer events

    Security:
    - Verifies webhook signature (inside processor)
    - Idempotent processing
    - Comprehensive error handling

    Args:
        request: Raw HTTP request
        stripe_signature: Stripe signature header
        db: Database session
        webhook: Webhook processor (handles signature verification + processing)

    Returns:
        200 OK on success, 400 on signature error, 500 on processing error
    """
    try:
        payload = await request.body()
    except Exception:
        return Response(status_code=400)

    if not stripe_signature:
        return Response(status_code=400)

    try:
        await webhook.process_webhook(db, payload, stripe_signature)
        return Response(status_code=200)
    except ValueError:
        return Response(status_code=400)
    except Exception:
        return Response(status_code=500)
