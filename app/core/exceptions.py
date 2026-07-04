from fastapi import Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, detail: str = "Resource not found"):
        self.detail = detail


class ConflictError(Exception):
    def __init__(self, detail: str = "Conflict"):
        self.detail = detail


class ValidationError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


class RateLimitError(Exception):
    def __init__(self, retry_after: int = 3600):
        self.retry_after = retry_after


class ProviderError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content=_error_body("NOT_FOUND", exc.detail))


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content=_error_body("CONFLICT", exc.detail))


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=_error_body("VALIDATION_ERROR", exc.detail))


async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(exc.retry_after)},
        content=_error_body("RATE_LIMIT_EXCEEDED", "Too many requests"),
    )
