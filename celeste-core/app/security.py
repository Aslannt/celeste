from fastapi import Header, HTTPException, status

from app.config import Settings


def require_token(x_celeste_token: str | None = Header(default=None)) -> None:
    expected = Settings.from_env().api_token
    if not x_celeste_token or x_celeste_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Celeste-Token",
        )
