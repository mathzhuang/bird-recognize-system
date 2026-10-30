from __future__ import annotations

import base64
import json
from typing import Any

from app.api.errors import ApiException


def encode_cursor(scope: dict[str, Any], last: list[Any]) -> str:
    payload = json.dumps({"scope": scope, "last": last}, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None, scope: dict[str, Any], expected_items: int) -> list[Any] | None:
    if cursor is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        payload = json.loads(raw.decode("utf-8"))
        last = payload["last"]
        if payload["scope"] != scope or not isinstance(last, list) or len(last) != expected_items:
            raise ValueError("cursor scope mismatch")
        return last
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiException(400, "invalid_cursor", "The cursor is invalid or belongs to a different query.") from exc
