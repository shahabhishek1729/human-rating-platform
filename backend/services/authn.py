from __future__ import annotations

from fastapi import HTTPException
import jwt
from jwt import PyJWTError, PyJWKClient

from config import Settings


async def verify_clerk_token_and_get_email(token: str, settings: Settings) -> str:
    """Verify a Clerk-issued JWT and return the embedded email claim.

    Security:
    - Resolves signing key via Clerk JWKS (kid → JWK → key)
    - Enforces both issuer and audience from settings.clerk
    - Uses RS256; rejects invalid signature or claims
    """
    issuer = (settings.clerk.issuer or "").strip()
    jwks_url = (settings.clerk.jwks_url or "").strip()
    audience = (settings.clerk.audience or "").strip()
    if not issuer or not jwks_url or not audience:
        raise HTTPException(status_code=500, detail="Clerk configuration is missing")

    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
        )
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token signature or claims")
    except Exception:
        raise HTTPException(status_code=401, detail="Failed to verify token")

    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(status_code=401, detail="Email claim missing in token")

    return email.strip()
