"""Small in-memory sliding-window rate limiter.

Note: state lives in this process only, so limits hold per API instance (use Redis to share them
across several instances).
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(key: str, limit: int, window_seconds: int):
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {retry} s.",
                                headers={"Retry-After": str(retry)})
        q.append(now)


def limit(scope: str, limit_: int, window_seconds: int):
    """FastAPI dependency: limit_ requests per window per client IP."""
    def dep(request: Request):
        check(f"{scope}:{client_ip(request)}", limit_, window_seconds)
    return dep


def reset():
    with _lock:
        _hits.clear()
