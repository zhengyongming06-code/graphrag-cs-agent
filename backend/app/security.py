from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import get_settings


def require_admin(
    x_service_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Write / session-dump / eval gate. Always requires a matching token.

    RuoYi should send X-Service-Token. The demo UI still uses X-Admin-Token.
    Default APP_SECRET is no longer a free pass.
    """
    settings = get_settings()
    expected = (settings.app_secret or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="未配置 APP_SECRET")
    token = (x_service_token or x_admin_token or "").strip()
    if not token or token != expected:
        raise HTTPException(
            status_code=401,
            detail="需要服务 Token：请求头 X-Service-Token 或 X-Admin-Token",
        )
