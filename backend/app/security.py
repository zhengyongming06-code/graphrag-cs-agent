from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Simple admin gate for write / eval endpoints."""
    settings = get_settings()
    expected = settings.app_secret
    if not expected or expected == "change-me-in-production":
        # demo mode: allow but still accept header if provided
        return
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="需要管理员 Token：请求头 X-Admin-Token")
