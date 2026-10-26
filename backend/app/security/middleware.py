"""Commercial Security Headers, Request Body Size Guard, and Sliding-Window Rate Limiter."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SlidingWindowRateLimiter:
    """Thread-safe per-client sliding-window request rate limiter."""

    def __init__(self, max_requests_per_minute: int) -> None:
        self._limit = max(1, max_requests_per_minute)
        self._window_seconds = 60.0
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow_request(self, client_key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            q = self._hits.setdefault(client_key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self._limit:
                return False, 0
            q.append(now)
            remaining = max(0, self._limit - len(q))
            return True, remaining


class SecurityAndQuotaMiddleware(BaseHTTPMiddleware):
    """Enforces upload size limits, per-client rate limits, and security response headers."""

    def __init__(
        self,
        app: object,
        max_body_bytes: int = 2_097_152,
        rate_limit_per_minute: int = 120,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_body_bytes = max_body_bytes
        self._limiter = SlidingWindowRateLimiter(rate_limit_per_minute)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], object]
    ) -> Response:
        # 1. Check Content-Length header against upload size limit
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_body_bytes:
                    return JSONResponse(
                        status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                        content={
                            "detail": {
                                "message": f"Request payload exceeds maximum allowed size of {self._max_body_bytes} bytes.",
                                "error_type": "PayloadTooLargeError",
                            }
                        },
                    )
            except ValueError:
                pass

        # 2. Enforce per-client sliding-window rate limit
        client_host = request.client.host if request.client else "local"
        auth_part = request.headers.get("Authorization", "")[-16:]
        client_key = f"{client_host}:{auth_part}"
        allowed, remaining = self._limiter.allow_request(client_key)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": "60"},
                content={
                    "detail": {
                        "message": "Rate limit exceeded. Please wait before sending additional requests.",
                        "error_type": "RateLimitExceededError",
                    }
                },
            )

        # 3. Verify actual body length for write requests
        if request.method in ("POST", "PUT", "PATCH"):
            body_bytes = await request.body()
            if len(body_bytes) > self._max_body_bytes:
                return JSONResponse(
                    status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                    content={
                        "detail": {
                            "message": f"Request payload ({len(body_bytes)} bytes) exceeds maximum allowed size of {self._max_body_bytes} bytes.",
                            "error_type": "PayloadTooLargeError",
                        }
                    },
                )

        response: Response = await call_next(request)  # type: ignore[assignment]

        # 4. Attach hardened security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
