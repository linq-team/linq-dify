import json
import time

import httpx
import pytest
from dify_plugin.entities.trigger import Subscription
from dify_plugin.errors.trigger import (
    SubscriptionError,
    TriggerDispatchError,
    TriggerValidationError,
)

from provider.linq_trigger import LinqSubscriptionConstructor, LinqTrigger
from webhooks import inbound_message, verify_request


def test_signed_unicode_payload(signed_request):
    request, secret = signed_request()
    event = verify_request(request, secret)
    message = inbound_message(event)
    assert message["text"] == "Hello, 世界 🌍"
    assert message["reply_idempotency_key"] == "dify-reply:message-1"
    assert message["line"] == "+15555550100"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"signature": "v1,invalid"},
        {"timestamp": 0},
        {"timestamp": int(time.time()) + 10000},
        {"method": "GET"},
        {"timestamp": "not-an-integer"},
        {"raw": b"x" * (1024 * 1024 + 1)},
    ],
)
def test_bad_requests_rejected(signed_request, kwargs):
    request, secret = signed_request(**kwargs)
    with pytest.raises(TriggerValidationError):
        verify_request(request, secret)


@pytest.mark.parametrize("secret", ["", "whsec_@@bad", None])
def test_bad_secret_rejected(signed_request, secret):
    request, _ = signed_request()
    with pytest.raises(TriggerValidationError):
        verify_request(request, secret)


def test_rotated_signatures_supported(signed_request):
    request, secret = signed_request()
    valid = request.headers["webhook-signature"]
    request, secret = signed_request(signature=f"v1,old {valid}")
    assert verify_request(request, secret)["event_id"] == "event-1"


def test_signed_malformed_json_rejected(signed_request):
    request, secret = signed_request(raw=b"{not json")
    with pytest.raises(TriggerDispatchError):
        verify_request(request, secret)


@pytest.mark.parametrize(
    "patch",
    [
        {"direction": "outbound"},
        {"sender_handle": {"is_me": True}},
        {"reconciled_at": "2026-11-05T20:00:00Z"},
        {"zero_retention": True},
    ],
)
def test_ignored_messages(event, patch):
    event["data"].update(patch)
    assert inbound_message(event) is None


def test_unknown_events_ignored(event):
    event["event_type"] = "message.sent"
    assert inbound_message(event) is None


def test_old_payload_does_not_silently_drop_message(event):
    del event["data"]["direction"]
    with pytest.raises(TriggerDispatchError, match="version=2026-02-03"):
        inbound_message(event)


def test_media_only_and_group_message(event):
    event["data"]["parts"] = [{"type": "media", "url": "https://example.com/image.png"}]
    event["data"]["chat"]["is_group"] = True
    message = inbound_message(event)
    assert message["text"] == "" and message["is_group"] is True
    assert message["parts"][0]["url"] == "https://example.com/image.png"


def test_dispatch_uses_signed_payload(signed_request):
    request, secret = signed_request()
    result = LinqTrigger(runtime=None).dispatch_event(
        Subscription(
            endpoint="https://dify.example/webhook", properties={"signing_secret": secret}
        ),
        request,
    )
    assert result.events == ["message_received"]
    assert result.payload["chat_id"] == "chat-1"
    assert result.response.status_code == 200


def test_subscription_creation_version_and_filter(api):
    requests, responses = api
    responses.append(httpx.Response(201, json={"id": "sub-1", "signing_secret": "whsec_secret"}))
    subscription = LinqSubscriptionConstructor(runtime=None).create_subscription(
        "https://dify.example/hook?token=abc&version=old",
        {"phone_numbers": "+15555550100"},
        {"api_key": "test-key"},
        "api-key",
    )
    body = json.loads(requests[0].content)
    assert body == {
        "target_url": "https://dify.example/hook?token=abc&version=2026-02-03",
        "subscribed_events": ["message.received"],
        "phone_numbers": ["+15555550100"],
    }
    assert subscription.properties["subscription_id"] == "sub-1"


def test_invalid_endpoint_never_creates_subscription(api):
    requests, _ = api
    with pytest.raises(SubscriptionError):
        LinqSubscriptionConstructor(runtime=None).create_subscription(
            "http://dify.example/hook", {}, {"api_key": "test-key"}, "api-key"
        )
    assert not requests


@pytest.mark.parametrize("status,success", [(204, True), (404, True), (403, False)])
def test_subscription_delete(api, status, success):
    requests, responses = api
    responses.append(httpx.Response(status))
    result = LinqSubscriptionConstructor(runtime=None).delete_subscription(
        Subscription(endpoint="https://dify.example/hook", properties={"subscription_id": "sub-1"}),
        {"api_key": "test-key"},
        "api-key",
    )
    assert requests[0].method == "DELETE"
    assert result.success is success
