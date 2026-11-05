import httpx
import pytest
from dify_plugin import DifyPluginEnv
from dify_plugin.core.plugin_registration import PluginRegistration
from dify_plugin.entities.tool import ToolRuntime

from scripts.package import stage_plugin


@pytest.fixture
def tool_stage(tmp_path, monkeypatch):
    staged = stage_plugin("linq", tmp_path / "linq")
    monkeypatch.chdir(staged)
    return staged


def test_sdk_loads_all_tools(tool_stage):
    registration = PluginRegistration(DifyPluginEnv())
    assert set(registration.tools_mapping["linq"][2]) == {
        "send_message",
        "list_phone_numbers",
        "get_chat",
        "list_messages",
        "mark_read",
        "set_typing",
    }
    assert not registration.triggers_configuration


def test_sdk_loads_trigger_separately(tmp_path, monkeypatch):
    staged = stage_plugin("linq_trigger", tmp_path / "linq_trigger")
    monkeypatch.chdir(staged)
    registration = PluginRegistration(DifyPluginEnv())
    assert not registration.tools_mapping
    assert len(registration.triggers_configuration) == 1
    trigger = registration.triggers_configuration[0]
    assert trigger.identity.name == "linq_trigger"
    assert [event.identity.name for event in trigger.events] == ["message_received"]


def test_manifest_requests_no_storage(tool_stage):
    registration = PluginRegistration(DifyPluginEnv())
    assert registration.configuration.resource.permission.storage is None


@pytest.mark.parametrize(
    "name,parameters,method,path",
    [
        (
            "send_message",
            {"chat_id": "c1", "text": "Hello", "idempotency_key": "reply:m1"},
            "POST",
            "/chats/c1/messages",
        ),
        ("list_phone_numbers", {}, "GET", "/phone_numbers"),
        ("get_chat", {"chat_id": "c1"}, "GET", "/chats/c1"),
        (
            "list_messages",
            {"chat_id": "c1", "limit": 2, "cursor": "next"},
            "GET",
            "/chats/c1/messages",
        ),
        ("mark_read", {"chat_id": "c1"}, "POST", "/chats/c1/read"),
        ("set_typing", {"chat_id": "c1", "action": "start"}, "POST", "/chats/c1/typing"),
        ("set_typing", {"chat_id": "c1", "action": "stop"}, "DELETE", "/chats/c1/typing"),
    ],
)
def test_tools_invoke_through_sdk(api, tool_stage, name, parameters, method, path):
    requests, responses = api
    responses.append(httpx.Response(200, json={"chat_id": "c1", "message": {"id": "m1"}}))
    registration = PluginRegistration(DifyPluginEnv())
    _, tool_class = registration.tools_mapping["linq"][2][name]
    tool = tool_class(
        runtime=ToolRuntime(
            credentials={"api_key": "test-key"}, user_id="test", session_id="session"
        ),
        session=None,
    )
    messages = list(tool.invoke(parameters))
    assert messages[0].type.value == "json"
    assert requests[0].method == method
    assert requests[0].url.path == "/api/partner/v3" + path
    if name == "send_message":
        assert len(messages) == 6
        assert messages[-1].message.variable_value == "accepted"
