import base64
import hashlib
import hmac
import json
import time

import dify_plugin  # noqa: F401 -- initialize the SDK/gevent before HTTP clients
import httpx
import pytest
from werkzeug import Request


@pytest.fixture
def api(monkeypatch):
    requests = []
    responses = []
    original_client = httpx.Client

    def handle(request):
        requests.append(request)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def client(**kwargs):
        return original_client(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr("linq_client.httpx.Client", client)
    monkeypatch.setattr("linq_client.time.sleep", lambda _: None)
    return requests, responses


@pytest.fixture
def event():
    return {
        "event_type": "message.received",
        "event_id": "event-1",
        "data": {
            "id": "message-1",
            "direction": "inbound",
            "chat": {
                "id": "chat-1",
                "is_group": False,
                "owner_handle": {"handle": "+15555550100", "is_me": True},
            },
            "sender_handle": {"handle": "+15555550101", "is_me": False},
            "service": "iMessage",
            "parts": [{"type": "text", "value": "Hello, 世界 🌍"}],
            "sent_at": "2026-11-05T20:00:00Z",
        },
    }


@pytest.fixture
def signed_request(event):
    secret = "whsec_" + base64.b64encode(b"synthetic-test-secret-32-bytes-key").decode()

    def build(payload=None, timestamp=None, signature=None, method="POST", raw=None):
        raw = raw if raw is not None else json.dumps(payload or event, ensure_ascii=False).encode()
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        signed = f"event-1.{timestamp}.".encode() + raw
        expected = base64.b64encode(
            hmac.new(base64.b64decode(secret[6:]), signed, hashlib.sha256).digest()
        ).decode()
        return Request.from_values(
            method=method,
            data=raw,
            content_type="application/json",
            headers={
                "webhook-id": "event-1",
                "webhook-timestamp": timestamp,
                "webhook-signature": signature or f"v1,{expected}",
            },
        ), secret

    return build
