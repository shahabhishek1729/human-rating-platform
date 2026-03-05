from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response

from config import Settings, get_settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_json(obj: dict) -> str:
    return _b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _unb64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _unb64url_json(data: str) -> dict:
    return json.loads(_unb64url(data))


def _sign(secret: str, payload: str) -> str:
    return _b64url(hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), sha256).digest())


class AdminSession:
    def __init__(self, email: str, issued_at: int, expires_at: int | None = None):
        self.email = email
        self.issued_at = issued_at
        self.expires_at = expires_at


class AdminSessionManager:
    """Lightweight, stateless, signed session cookie for admin access.

    Cookie format: v1.<payload>.<signature>
      - payload: base64url({"email": str, "iat": int, "exp": int})
      - signature: base64url(HMAC_SHA256(secret, payload))
    """

    VERSION = "v1"

    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def cookie_name(self) -> str:
        return self._settings.hrp_session_cookie

    def _encode(self, email: str) -> str:
        now = int(time.time())
        exp = now + int(self._settings.hrp_session_max_age)
        payload = _b64url_json({"email": email, "iat": now, "exp": exp})
        sig = _sign(self._settings.app_secret_key, payload)
        return f"{self.VERSION}.{payload}.{sig}"

    def _decode(self, token: str) -> Optional[AdminSession]:
        try:
            ver, payload, sig = token.split(".")
        except ValueError:
            return None
        if ver != self.VERSION:
            return None
        expected = _sign(self._settings.app_secret_key, payload)
        if not hmac.compare_digest(expected, sig):
            return None
        data = _unb64url_json(payload)
        email = data.get("email")
        iat = data.get("iat")
        exp = data.get("exp")
        if not isinstance(email, str) or not email:
            return None
        try:
            iat = int(iat)
            exp = int(exp)
        except Exception:
            return None
        # Enforce server-side expiration regardless of browser cookie behavior
        now = int(time.time())
        if now > exp:
            return None
        return AdminSession(email=email, issued_at=iat, expires_at=exp)

    def set_cookie(self, response: Response, email: str) -> None:
        value = self._encode(email)
        # Use SameSite=None only when cookies are Secure (production, cross-site).
        # In local dev, sending a Secure cookie over http://localhost is rejected by browsers,
        # and SameSite=None without Secure is also rejected; use Lax for dev/proxy.
        same_site = "none" if self._settings.cookie_secure else "lax"
        response.set_cookie(
            key=self.cookie_name,
            value=value,
            max_age=self._settings.hrp_session_max_age,
            httponly=True,
            secure=self._settings.cookie_secure,
            samesite=same_site,
            path="/",
        )

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(self.cookie_name, path="/")

    def get_session(self, request: Request) -> Optional[AdminSession]:
        token = request.cookies.get(self.cookie_name)
        if not token:
            return None
        return self._decode(token)


def get_admin_manager(settings: Settings = Depends(get_settings)) -> AdminSessionManager:
    return AdminSessionManager(settings)


async def require_admin(
    request: Request,
    settings: Settings = Depends(get_settings),
    manager: AdminSessionManager = Depends(get_admin_manager),
) -> AdminSession:
    # Allow bypass in test/dev when explicitly disabled
    if not settings.admin_auth_enabled:
        return AdminSession(email="dev@local", issued_at=0)

    session = manager.get_session(request)
    if not session:
        raise HTTPException(status_code=403, detail="Admin session required")

    email = session.email.lower().strip()
    allow = {e.strip().lower() for e in settings.admin_allowlist}
    if not email or email not in allow:
        raise HTTPException(status_code=403, detail="Not allowlisted for admin access")

    return session
