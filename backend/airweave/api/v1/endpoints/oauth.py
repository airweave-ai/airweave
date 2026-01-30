"""OAuth 2.1 authorization server endpoints for MCP."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi_auth0 import Auth0User
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.auth import auth0
from airweave.api.deps import get_db
from airweave.core.config import settings
from airweave.core.oauth_service import OAuthService, OAuthServiceError

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/.well-known/oauth-authorization-server", response_model=schemas.OAuthServerMetadata)
async def get_oauth_metadata() -> schemas.OAuthServerMetadata:
    """OAuth 2.1 Authorization Server Metadata (RFC 8414).

    This endpoint advertises OAuth capabilities to MCP clients.
    """
    # Determine the base URL (use API_FULL_URL if set, otherwise construct from request)
    base_url = settings.API_FULL_URL or "https://api.airweave.ai"

    return schemas.OAuthServerMetadata(
        issuer=base_url,
        authorization_endpoint=f"{base_url}/oauth/authorize",
        token_endpoint=f"{base_url}/oauth/token",
        revocation_endpoint=f"{base_url}/oauth/revoke",
        grant_types_supported=["authorization_code"],
        response_types_supported=["code"],
        code_challenge_methods_supported=["S256"],
        token_endpoint_auth_methods_supported=["none"],  # Public clients
    )


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("read:collection"),
    state: str = Query(...),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth0_user: Auth0User = Depends(auth0.get_user),
):
    """OAuth authorization endpoint.

    This endpoint:
    1. Validates the user is authenticated (via Auth0)
    2. Validates the client_id and redirect_uri
    3. Redirects to the frontend consent screen

    The user will then approve or deny the authorization request.
    """
    # Validate response_type
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Invalid response_type. Must be 'code'.")

    # Validate client exists
    try:
        client = await crud.oauth_client.get_by_client_id(db, client_id=client_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    # Validate redirect_uri
    if not crud.oauth_client.validate_redirect_uri(client, redirect_uri):
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")

    # Get user from Auth0
    user = await crud.user.get_by_email(db, email=auth0_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Redirect to frontend consent screen with all parameters
    frontend_url = settings.API_FULL_URL.replace("api.", "app.") if settings.API_FULL_URL else "https://app.airweave.ai"
    
    # Build consent URL with query parameters
    consent_params = f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
    if code_challenge:
        consent_params += f"&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}"
    
    consent_url = f"{frontend_url}/oauth/consent?{consent_params}"
    
    return Response(status_code=302, headers={"Location": consent_url})


@router.post("/authorize")
async def approve_authorization(
    approved: bool = Form(...),
    collection_id: UUID = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(...),
    scope: str = Form("read:collection"),
    code_challenge: Optional[str] = Form(None),
    code_challenge_method: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    auth0_user: Auth0User = Depends(auth0.get_user),
):
    """Process user's consent decision.

    After the user approves or denies on the consent screen,
    this endpoint generates an authorization code (if approved)
    and redirects back to the client.
    """
    # If user denied, redirect with error
    if not approved:
        error_redirect = f"{redirect_uri}?error=access_denied&state={state}"
        return Response(status_code=302, headers={"Location": error_redirect})

    # Get user
    user = await crud.user.get_by_email(db, email=auth0_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate user has access to collection
    collection = await crud.collection.get(db, id=collection_id)
    if not collection or collection.organization_id not in [
        uo.organization_id for uo in user.user_organizations
    ]:
        raise HTTPException(status_code=403, detail="No access to this collection")

    # Get primary organization
    org_id = user.primary_organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no primary organization")

    try:
        # Create authorization code
        code, redirect_url = await OAuthService.create_authorization_code(
            db,
            user_id=user.id,
            organization_id=org_id,
            client_id=client_id,
            collection_id=collection_id,
            redirect_uri=redirect_uri,
            scope=scope,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )

        # Redirect to client with code
        return Response(status_code=302, headers={"Location": redirect_url})

    except OAuthServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/token", response_model=schemas.OAuthTokenResponse)
async def exchange_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Token endpoint - exchange authorization code for access token.

    This endpoint:
    1. Validates the authorization code
    2. Verifies PKCE if present
    3. Generates and returns an access token
    """
    # Validate grant_type
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Invalid grant_type")

    try:
        # Exchange code for token
        token_response = await OAuthService.exchange_code_for_token(
            db,
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

        return token_response

    except OAuthServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/revoke")
async def revoke_token(
    token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an OAuth access token.

    This endpoint allows users or administrators to revoke access tokens,
    immediately invalidating them.
    """
    try:
        await OAuthService.revoke_access_token(db, token=token)
        return {"message": "Token revoked successfully"}
    except OAuthServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate")
async def validate_token(
    token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Validate an OAuth access token (for MCP server use).

    This endpoint is called by the MCP server to validate tokens
    and retrieve associated user/collection information.
    """
    try:
        user_id, org_id, collection_id = await OAuthService.validate_access_token(db, token=token)
        
        return {
            "valid": True,
            "user_id": str(user_id),
            "organization_id": str(org_id),
            "collection_id": str(collection_id),
        }
    except OAuthServiceError as e:
        raise HTTPException(status_code=401, detail=str(e))
