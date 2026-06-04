"""统一业务错误（HTTPException + 结构化 detail）。

错误码清单见 feature-clarifications §二十三。service 层直接抛 HTTPException，
detail 形如 {"code", "message", "field"?}（api-specification §4.4）。
"""

from __future__ import annotations

from fastapi import HTTPException, status


def app_error(status_code: int, code: str, message: str, field: str | None = None) -> HTTPException:
    detail: dict[str, str] = {"code": code, "message": message}
    if field is not None:
        detail["field"] = field
    return HTTPException(status_code=status_code, detail=detail)


def bad_request(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_400_BAD_REQUEST, code, message, field)


def not_found(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_404_NOT_FOUND, code, message, field)


def conflict(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_409_CONFLICT, code, message, field)


def precondition_failed(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_412_PRECONDITION_FAILED, code, message, field)


def unprocessable(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_422_UNPROCESSABLE_ENTITY, code, message, field)


def gone(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_410_GONE, code, message, field)


def payload_too_large(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, code, message, field)


def unauthorized(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_401_UNAUTHORIZED, code, message, field)


def forbidden(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_403_FORBIDDEN, code, message, field)


def payment_required(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_402_PAYMENT_REQUIRED, code, message, field)
