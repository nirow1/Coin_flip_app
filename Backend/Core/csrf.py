import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_EXEMPT_PATHS = frozenset(
    {
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
        "/wallet/webhook/solana",
    }
)


def _tokens_match(cookie: str | None, header: str | None) -> bool:
    if not cookie or not header:
        return False
    try:
        return hmac.compare_digest(cookie, header)
    except (TypeError, ValueError):
        return False


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if (
            request.method in _UNSAFE_METHODS
            and request.url.path not in _EXEMPT_PATHS
        ):
            cookie = request.cookies.get("csrf_token")
            header = request.headers.get("x-csrf-token")
            if not _tokens_match(cookie, header):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF check failed"},
                )
        return await call_next(request)
