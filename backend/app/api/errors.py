from __future__ import annotations

import json
import logging
import uuid
from functools import wraps
from typing import Any, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from starlette.requests import ClientDisconnect
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger("bird_api")


class ApiException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


class ContractRoute(APIRoute):
    def get_route_handler(self) -> Callable[..., Any]:
        original_handler = super().get_route_handler()

        @wraps(original_handler)
        async def contract_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except ApiException as exc:
                return _error_response(request, exc.status_code, exc.code, exc.message, exc.details, exc.headers)
            except RequestValidationError as exc:
                fields = [
                    {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
                    for error in exc.errors()
                ]
                return _error_response(request, 400, "invalid_request", "The request contains invalid fields.", {"fields": fields})
            except ClientDisconnect:
                return _error_response(request, 400, "upload_interrupted", "The client disconnected before the request was completely received.")
            except StarletteHTTPException as exc:
                status = exc.status_code if exc.status_code in {400, 404, 409, 413, 415, 416, 507} else 500
                code = {
                    400: "invalid_request",
                    404: "not_found",
                    409: "conflict",
                    413: "payload_too_large",
                    415: "unsupported_media_type",
                    416: "invalid_range",
                    507: "insufficient_storage",
                }.get(status, "internal_error")
                message = str(exc.detail) if status != 500 else "The local service encountered an unexpected error."
                return _error_response(request, status, code, message, headers=exc.headers)
            except Exception:
                logger.exception("Unexpected API error for %s %s", request.method, request.url.path)
                return _error_response(request, 500, "internal_error", "The local service encountered an unexpected error.")

        return contract_handler


def error_envelope(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=json.loads(json.dumps(error_envelope(request, status_code, code, message, details), allow_nan=False)),
        headers=headers,
    )
