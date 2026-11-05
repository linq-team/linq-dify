"""Linq Standard Webhooks verification and event normalization."""

import base64
import binascii
import hashlib
import hmac
import json
import re
import time

from dify_plugin.errors.trigger import TriggerDispatchError, TriggerValidationError


def verify_request(request, secret: str, now: float | None = None) -> dict:
    if request.method != "POST":
        raise TriggerValidationError("Linq webhooks require POST.")
    raw = request.get_data()
    if len(raw) > 1024 * 1024:
        raise TriggerValidationError("Linq webhook exceeds the 1 MiB limit.")
    event_id = request.headers.get("webhook-id", "")
    timestamp = request.headers.get("webhook-timestamp", "")
    signatures = request.headers.get("webhook-signature", "").split()
    if not event_id or len(event_id) > 256 or not re.fullmatch(r"[0-9]{1,12}", timestamp):
        raise TriggerValidationError("Missing or invalid Linq webhook headers.")
    if abs((time.time() if now is None else now) - int(timestamp)) > 300:
        raise TriggerValidationError("Linq webhook timestamp is outside the five-minute window.")
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except (ValueError, AttributeError, binascii.Error):
        raise TriggerValidationError("The Linq signing secret is invalid.") from None
    if not key:
        raise TriggerValidationError("The Linq signing secret is missing.")
    signed = f"{event_id}.{timestamp}.".encode() + raw
    expected = b"v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest())
    if not any(hmac.compare_digest(sig.encode(), expected) for sig in signatures):
        raise TriggerValidationError("Invalid Linq webhook signature.")
    try:
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise TriggerDispatchError("Linq webhook is not valid JSON.") from None
    if not isinstance(event, dict) or not isinstance(event.get("event_type"), str):
        raise TriggerDispatchError("Linq webhook must have an event_type.")
    # Use the signed delivery ID as the stable deduplication key.
    return {**event, "event_id": event_id}


def inbound_message(event: dict) -> dict | None:
    if event.get("event_type") != "message.received":
        return None
    data = event.get("data")
    if not isinstance(data, dict):
        raise TriggerDispatchError("Linq message.received has no message object.")
    if data.get("direction") == "outbound":
        return None
    if data.get("direction") != "inbound":
        raise TriggerDispatchError("Configure the webhook URL with version=2026-02-03.")
    sender, chat = data.get("sender_handle"), data.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        raise TriggerDispatchError("Linq message is missing its sender or chat.")
    if (
        sender.get("is_me") is True
        or data.get("reconciled_at")
        or data.get("zero_retention") is True
    ):
        return None
    if not all(
        isinstance(v, str) and v for v in (data.get("id"), chat.get("id"), sender.get("handle"))
    ):
        raise TriggerDispatchError("Linq message is missing required identifiers.")
    parts = data.get("parts")
    if not isinstance(parts, list):
        raise TriggerDispatchError("Linq message parts must be a list.")
    text = "\n".join(
        part["value"]
        for part in parts
        if isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("value"), str)
    )
    owner = chat.get("owner_handle") or {}
    return {
        "event_id": event["event_id"],
        "message_id": data["id"],
        "chat_id": chat["id"],
        "sender": sender["handle"],
        "line": owner.get("handle", "") if isinstance(owner, dict) else "",
        "text": text,
        "service": data.get("service") or "",
        "is_group": chat.get("is_group") is True,
        "sent_at": data.get("sent_at") or "",
        "parts": parts,
        "reply_idempotency_key": f"dify-reply:{data['id']}",
    }
