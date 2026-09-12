"""Domain exceptions and the handlers that turn them into HTTP responses.

Response shape is fixed by docs/API.md §10: ``{detail, code, context}``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class ClassTrackError(Exception):
    """Base class for expected, reportable failures."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "error"

    def __init__(self, message: str, *, detail: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(ClassTrackError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class NoActiveRoutineError(NotFoundError):
    code = "no_active_routine"

    def __init__(self, department: str) -> None:
        super().__init__(
            f"No active routine for department {department!r}. Ingest one first.",
            detail={"department": department},
        )


class ValidationError(ClassTrackError):
    status_code = 422
    code = "validation_error"


class IngestionError(ClassTrackError):
    """Raised when a routine document cannot be trusted.

    Ingestion fails loudly rather than importing a partial routine: a routine
    that is silently missing classes is worse than no routine at all.
    """

    status_code = 422
    code = "ingestion_error"


class AuthError(ClassTrackError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(ClassTrackError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ConflictError(ClassTrackError):
    """A scheduling conflict, or an action attempted outside its window."""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict_detected"


def register_exception_handlers(app: FastAPI) -> None:
    async def handle(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        assert isinstance(exc, ClassTrackError)
        body: dict[str, object] = {"detail": exc.message, "code": exc.code}
        if exc.detail is not None:
            body["context"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=body)

    app.add_exception_handler(ClassTrackError, handle)
