import json

import httpx
import pytest

from linq_client import API_BASE, LinqClient, LinqError, page_parameters, path_id


@pytest.mark.parametrize(
    "params,path,expected",
    [
        ({"chat_id": "chat-1"}, "/chats/chat-1/messages", {}),
        ({"to": "+15555550101"}, "/messages", {"to": ["+15555550101"]}),
        (
            {"to": "+15555550101, person@example.com", "from_number": "+15555550100"},
            "/chats",
            {"to": ["+15555550101", "person@example.com"], "from": "+15555550100"},
        ),
    ],
)
def test_send_routes_and_ids(api, params, path, expected):
    requests, responses = api
    responses.append(
        httpx.Response(201, json={"chat": {"id": "chat-1", "message": {"id": "message-1"}}})
    )
    result = LinqClient("test-key").send(
        {**params, "text": "Hello, 世界 🌍", "idempotency_key": "reply:1"}
    )
    request = requests[0]
    assert str(request.url) == API_BASE + path
    assert request.headers["Authorization"] == "Bearer test-key"
    assert json.loads(request.content) == {
        **expected,
        "message": {
            "parts": [{"type": "text", "value": "Hello, 世界 🌍"}],
            "idempotency_key": "reply:1",
        },
    }
    assert result["chat_id"] == "chat-1"
    assert result["message_id"] == "message-1"
    assert result["status"] == "accepted"


@pytest.mark.parametrize("status", [408, 425, 429, 500, 503])
def test_transient_errors_reuse_identical_send(api, status):
    requests, responses = api
    responses.extend(
        [
            httpx.Response(status),
            httpx.Response(201, json={"message": {"id": "m1"}, "chat_id": "c1"}),
        ]
    )
    LinqClient("test-key").send({"chat_id": "c1", "text": "Hello", "idempotency_key": "same-key"})
    assert len(requests) == 2
    assert requests[0].content == requests[1].content


def test_timeout_retries_and_caps_attempts(api):
    requests, responses = api
    responses.extend([httpx.ReadTimeout("secret key and body")] * 3)
    with pytest.raises(LinqError, match="same idempotency key") as error:
        LinqClient("test-key").request("GET", "/phone_numbers")
    assert len(requests) == 3
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 302])
def test_permanent_errors_not_retried_and_redacted(api, status):
    requests, responses = api
    responses.append(
        httpx.Response(
            status, text="test-key PRIVATE MESSAGE", headers={"Location": "https://evil.example"}
        )
    )
    with pytest.raises(LinqError, match=f"HTTP {status}") as error:
        LinqClient("test-key").request("GET", "/phone_numbers")
    assert len(requests) == 1
    assert "test-key" not in str(error.value) and "PRIVATE" not in str(error.value)


def test_long_retry_after_does_not_retry_early(api):
    requests, responses = api
    responses.append(httpx.Response(429, headers={"Retry-After": "60"}))
    with pytest.raises(LinqError):
        LinqClient("test-key").request("GET", "/phone_numbers")
    assert len(requests) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"chat_id": "c1", "to": "+15555550101"},
        {"chat_id": "c1", "from_number": "+15555550100"},
        {"chat_id": "../escape"},
        {"chat_id": "https://evil.example"},
        {"chat_id": "c1", "text": ""},
        {"chat_id": "c1", "idempotency_key": ""},
        {"chat_id": "c1", "idempotency_key": "x" * 256},
        {"to": "555-1234"},
        {"to": "+15555550101,+15555550101"},
        {"to": "+15555550101,"},
        {"to": "+15555550101", "from_number": "not-a-phone"},
        {},
    ],
)
def test_invalid_send_never_calls_network(api, patch):
    requests, _ = api
    with pytest.raises(LinqError):
        LinqClient("test-key").send({"text": "hello", "idempotency_key": "key", **patch})
    assert not requests


@pytest.mark.parametrize("value", [0, 101, 1.5, True, "x", None])
def test_bad_page_sizes(value):
    with pytest.raises(LinqError):
        page_parameters({"limit": value})


def test_pagination_and_path_validation():
    assert page_parameters({"limit": 20.0, "cursor": "next-token"}) == {
        "limit": 20,
        "cursor": "next-token",
    }
    for value in ("../secrets", "a/b", "a?b", "a#b", "a%2Fb", ""):
        with pytest.raises(LinqError):
            path_id(value)


def test_invalid_success_json_is_redacted(api):
    _, responses = api
    responses.append(httpx.Response(200, text="secret content"))
    with pytest.raises(LinqError, match="invalid JSON") as error:
        LinqClient("test-key").request("GET", "/phone_numbers")
    assert "secret content" not in str(error.value)


def test_no_retry_for_subscription_creation(api):
    requests, responses = api
    responses.append(httpx.ReadTimeout("secret"))
    with pytest.raises(LinqError):
        LinqClient("test-key").request("POST", "/webhook-subscriptions", body={}, retry=False)
    assert len(requests) == 1


def test_chat_still_creating_retries_with_the_same_send(api):
    requests, responses = api
    responses.extend(
        [
            httpx.Response(409, json={"error": {"code": 2009, "message": "still creating"}}),
            httpx.Response(201, json={"chat_id": "c1", "message": {"id": "m1"}}),
        ]
    )
    result = LinqClient("test-key").send(
        {"chat_id": "c1", "text": "Hello", "idempotency_key": "same-key"}
    )
    assert result["message_id"] == "m1"
    assert len(requests) == 2
    assert requests[0].content == requests[1].content


def test_other_conflicts_are_not_retried(api):
    requests, responses = api
    responses.append(httpx.Response(409, json={"error": {"code": 2015}}))
    with pytest.raises(LinqError):
        LinqClient("test-key").request("GET", "/phone_numbers")
    assert len(requests) == 1


@pytest.mark.parametrize("body", ["", "{}", '{"chat_id":"c1"}', '{"chat":[]}'])
def test_malformed_success_does_not_report_send_accepted(api, body):
    _, responses = api
    responses.append(httpx.Response(200, text=body))
    with pytest.raises(LinqError, match="same idempotency key"):
        LinqClient("test-key").send(
            {"chat_id": "c1", "text": "Hello", "idempotency_key": "same-key"}
        )
