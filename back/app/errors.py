"""Uniform error bodies for forms: {"detail": str, "errors": [{"field", "message"}]}.

The default FastAPI 422 body echoes the submitted input back, which would
include plain-text passwords; this handler returns messages only.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class FormError(Exception):
    def __init__(self, status_code: int, detail: str, errors: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        self.errors = errors or {}


def _field_name(loc: tuple) -> str:
    parts = [str(part) for part in loc if part != "body"]
    return ".".join(parts) or "body"


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": _field_name(error["loc"]), "message": error["msg"].removeprefix("Value error, ")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Invalid input", "errors": errors})


async def form_error_handler(_: Request, exc: FormError) -> JSONResponse:
    errors = [{"field": field, "message": message} for field, message in exc.errors.items()]
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "errors": errors})
