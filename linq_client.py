"""Small, fixed-origin client for Linq Partner API v3."""

import re
import time
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

API_ORIGIN = "https://api.linqapp.com"
API_BASE = API_ORIGIN + "/api/partner/v3"
RETRY_DELAYS = (0.5, 2.0)


class LinqError(ValueError):
    """A safe error for Dify: never includes HTTP bodies or credentials."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LinqError(f"{name} is required and must be text.")
    return value


def path_id(value: Any, name: str = "chat_id") -> str:
    value = required_text(value, name).strip()
    # IDs are single path segments; never allow traversal or URL injection.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise LinqError(f"{name} is not a valid Linq identifier.")
    return quote(value, safe="")


def phone_number(value: str) -> str:
    if not re.fullmatch(r"\+[1-9][0-9]{1,14}", value):
        raise LinqError("Phone numbers must use E.164 format, for example +14155550123.")
    return value


def recipients(value: Any) -> list[str]:
    value = required_text(value, "to")
    items = [item.strip() for item in value.split(",")]
    if not 1 <= len(items) <= 31 or len(set(items)) != len(items):
        raise LinqError("to must contain 1–31 distinct comma-separated recipients.")
    for item in items:
        if not re.fullmatch(r"\+[1-9][0-9]{1,14}|[^\s@,]+@[^\s@,]+\.[^\s@,]+", item):
            raise LinqError("Each recipient must be an E.164 phone number or email address.")
    return items


def page_parameters(parameters: dict) -> dict:
    raw = parameters.get("limit", 20)
    if isinstance(raw, bool):
        raise LinqError("limit must be an integer from 1 to 100.")
    try:
        limit = int(raw)
        if float(raw) != limit or not 1 <= limit <= 100:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise LinqError("limit must be an integer from 1 to 100.") from None
    result = {"limit": limit}
    if parameters.get("cursor"):
        result["cursor"] = required_text(parameters["cursor"], "cursor")
    return result


class LinqClient:
    def __init__(self, api_key: str):
        self.api_key = required_text(api_key, "Linq API key").strip()
        if any(c.isspace() for c in self.api_key):
            raise LinqError("Enter the API key without Bearer or whitespace.")

    def request(self, method: str, path: str, *, body=None, params=None, retry=True):
        if not path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise LinqError("Invalid Linq API path.")
        attempts = len(RETRY_DELAYS) + 1 if retry else 1
        for attempt in range(attempts):
            response = None
            try:
                # No environment proxies, redirects, arbitrary hosts, or cookies.
                with httpx.Client(
                    timeout=httpx.Timeout(10.0), follow_redirects=False, trust_env=False
                ) as client:
                    response = client.request(
                        method,
                        API_BASE + path,
                        json=body,
                        params=params,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Accept": "application/json",
                        },
                    )
            except httpx.TransportError:
                error = LinqError(
                    "Linq request timed out or could not connect. Retry with the same idempotency key when sending."
                )
                retryable = True
            else:
                if 200 <= response.status_code < 300:
                    if not response.content:
                        return {}
                    try:
                        result = response.json()
                    except ValueError:
                        raise LinqError(
                            "Linq returned an invalid JSON response. If sending, retry with the same idempotency key."
                        ) from None
                    if not isinstance(result, dict):
                        raise LinqError("Linq returned an unexpected response object.")
                    return result
                status = response.status_code
                hints = {
                    401: "Check the Linq API key.",
                    403: "The API key cannot perform this action or the recipient opted out.",
                    404: "Check the chat or subscription ID belongs to this account.",
                    429: "Linq rate limit reached. Retry later with the same idempotency key when sending.",
                }
                error = LinqError(
                    f"Linq API returned HTTP {status}. "
                    + hints.get(
                        status,
                        "Check the inputs and retry with the same idempotency key when sending.",
                    ),
                    status,
                )
                code = None
                if status == 409:
                    try:
                        payload = response.json()
                        detail = payload.get("error") if isinstance(payload, dict) else None
                        code = detail.get("code") if isinstance(detail, dict) else None
                    except ValueError:
                        pass
                retryable = (
                    status in (408, 425, 429) or status >= 500 or (status == 409 and code == 2009)
                )
            if not retryable or attempt == attempts - 1:
                raise error
            delay = RETRY_DELAYS[attempt]
            if response is not None:
                header = response.headers.get("Retry-After", "")
                try:
                    retry_after = float(header)
                except ValueError:
                    try:
                        retry_after = parsedate_to_datetime(header).timestamp() - time.time()
                    except (TypeError, ValueError, OverflowError):
                        retry_after = 0
                # Do not retry earlier than requested or block a plugin worker for minutes.
                if retry_after > 5:
                    raise error
                delay = max(delay, retry_after)
            time.sleep(delay)
        raise AssertionError("unreachable")

    def send(self, parameters: dict) -> dict:
        text = required_text(parameters.get("text"), "text")
        key = required_text(parameters.get("idempotency_key"), "idempotency_key")
        if len(key) > 255 or any(ord(c) < 32 for c in key):
            raise LinqError("idempotency_key must be 1–255 characters without control characters.")
        message = {"parts": [{"type": "text", "value": text}], "idempotency_key": key}
        chat_id, to, sender = (parameters.get(n) for n in ("chat_id", "to", "from_number"))
        if chat_id:
            if to or sender:
                raise LinqError(
                    "Use chat_id to reply, or to/from_number for a new send; do not combine them."
                )
            result = self.request(
                "POST", f"/chats/{path_id(chat_id)}/messages", body={"message": message}
            )
        else:
            body = {"to": recipients(to), "message": message}
            if sender:
                body["from"] = phone_number(required_text(sender, "from_number").strip())
            result = self.request("POST", "/chats" if sender else "/messages", body=body)
        raw_chat = result.get("chat")
        chat = raw_chat if isinstance(raw_chat, dict) else {}
        sent = result.get("message") or chat.get("message") or {}
        message_id = sent.get("id") if isinstance(sent, dict) else None
        result_chat_id = (
            result.get("chat_id") or (chat.get("id") if isinstance(chat, dict) else None) or chat_id
        )
        if (
            not isinstance(message_id, str)
            or not message_id
            or not isinstance(result_chat_id, str)
            or not result_chat_id
        ):
            raise LinqError(
                "Linq returned an invalid send response. Retry with the same idempotency key."
            )
        result_sender = result.get("from")
        return {
            "chat_id": result_chat_id,
            "message_id": message_id,
            "from_number": result_sender if isinstance(result_sender, str) else sender or "",
            "idempotency_key": key,
            "status": "accepted",
            "result": result,
        }
