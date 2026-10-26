"""OIDC-Compatible Authentication & Tenant Ownership Authorization (Fail-Closed in Production)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings

DEFAULT_DEV_USER_ID = "local-dev-user"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Authenticated user identity and commercial account plan tier."""

    user_id: str
    email: str = "engineer@localhost"
    name: str = "CAE Engineer"
    plan_tier: str = "pro"
    roles: list[str] = field(default_factory=lambda: ["engineer"])


_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def _decode_oidc_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and validate an OIDC/OAuth2 JWT using JWKS or shared secret."""
    has_jwks = bool(settings.oidc_jwks_url.strip())
    has_secret = bool(settings.oidc_jwt_secret.strip())

    if not has_jwks and not has_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication provider is not configured; failing closed.",
        )

    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": bool(settings.oidc_audience.strip()),
        "verify_iss": bool(settings.oidc_issuer_url.strip()),
    }
    decode_kwargs: dict[str, Any] = {
        "algorithms": settings.oidc_algorithms or ["RS256", "HS256"],
        "options": options,
    }
    if settings.oidc_audience.strip():
        decode_kwargs["audience"] = settings.oidc_audience.strip()
    if settings.oidc_issuer_url.strip():
        decode_kwargs["issuer"] = settings.oidc_issuer_url.strip()

    try:
        if has_jwks:
            jwks_url = settings.oidc_jwks_url.strip()
            if jwks_url not in _JWKS_CLIENTS:
                _JWKS_CLIENTS[jwks_url] = PyJWKClient(jwks_url)
            signing_key = _JWKS_CLIENTS[jwks_url].get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, signing_key, **decode_kwargs)
        else:
            claims = jwt.decode(
                token,
                settings.oidc_jwt_secret.strip(),
                **decode_kwargs,
            )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = str(claims.get("sub", "")).strip()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token is missing required 'sub' (subject) claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


def get_current_principal(request: Request) -> AuthenticatedPrincipal:
    """Resolve and authenticate the current caller.

    In production (APP_ENV == 'production' or AUTH_REQUIRED == True), authentication
    strictly fails closed if OIDC is unconfigured or if a valid Bearer JWT is absent.
    """
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    is_prod_or_strict = (
        settings.app_env.lower() == "production" or settings.auth_required
    )

    if is_prod_or_strict and not (
        settings.oidc_jwks_url.strip() or settings.oidc_jwt_secret.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication failed closed: OIDC provider credentials are not configured for production.",
        )

    auth_header: Optional[str] = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed Authorization header. Expected 'Bearer <JWT>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        claims = _decode_oidc_jwt(parts[1].strip(), settings)
        return AuthenticatedPrincipal(
            user_id=str(claims["sub"]).strip(),
            email=str(claims.get("email", "user@organization.com")),
            name=str(claims.get("name", claims["sub"])),
            plan_tier=str(claims.get("plan_tier", "pro")),
            roles=list(claims.get("roles", ["engineer"])),
        )

    if is_prod_or_strict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid OIDC Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Local development / test convenience header for multi-user isolation testing
    dev_user_override = request.headers.get("X-Debug-User-Id")
    if dev_user_override and dev_user_override.strip():
        uid = dev_user_override.strip()
        return AuthenticatedPrincipal(
            user_id=uid,
            email=f"{uid}@localhost",
            name=f"Dev User ({uid})",
            plan_tier=request.headers.get("X-Debug-Plan-Tier", "pro"),
        )

    return AuthenticatedPrincipal(user_id=DEFAULT_DEV_USER_ID)
