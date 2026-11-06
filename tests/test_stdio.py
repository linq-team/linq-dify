"""Exercise the installed SDK protocol in a fresh process, without real API traffic."""

import json
import os
import select
import subprocess
import sys
import time

import pytest

from scripts.package import stage_plugin

RUNNER = """
from dify_plugin import Plugin, DifyPluginEnv
import httpx

original_client = httpx.Client
def handle(request):
    assert request.url.host == "api.linqapp.com"
    assert request.headers["authorization"] == "Bearer synthetic-test-key"
    return httpx.Response(201, json={"chat_id":"test-chat", "message":{"id":"test-message"}})
def client(**kwargs):
    return original_client(transport=httpx.MockTransport(handle), **kwargs)
httpx.Client = client
Plugin(DifyPluginEnv()).run()
"""


@pytest.mark.parametrize("name", ["linq", "linq_trigger"])
def test_real_process_registers_and_serves_protocol(tmp_path, name):
    staged = stage_plugin(name, tmp_path / name)
    (staged / "test_runner.py").write_text(RUNNER)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DIFY_", "REMOTE_INSTALL_", "INSTALL_METHOD"))
    }
    env["INSTALL_METHOD"] = "local"
    with (tmp_path / "stderr.log").open("w+") as errors:
        process = subprocess.Popen(
            [sys.executable, "test_runner.py"],
            cwd=staged,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        pending = b""
        received = []

        def read():
            nonlocal pending
            deadline = time.monotonic() + 10
            while True:
                if b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if line.strip():
                        message = json.loads(line)
                        received.append(message)
                        return message
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                    errors.seek(0)
                    raise AssertionError(errors.read() + repr(received))
                data = os.read(process.stdout.fileno(), 65536)
                assert data, "Plugin process exited before responding"
                pending += data

        try:
            assert read()["name"] == name
            while read().get("event") != "heartbeat":
                pass
            if name == "linq":
                request = {
                    "session_id": "test-session",
                    "event": "request",
                    "data": {
                        "type": "tool",
                        "action": "invoke_tool",
                        "user_id": "test-user",
                        "provider": "linq",
                        "tool": "send_message",
                        "credentials": {"api_key": "synthetic-test-key"},
                        "tool_parameters": {
                            "chat_id": "test-chat",
                            "text": "Synthetic message",
                            "idempotency_key": "test-send",
                        },
                    },
                }
                process.stdin.write(json.dumps(request).encode() + b"\n")
                process.stdin.flush()
                events = []
                while True:
                    message = read()
                    if message.get("event") != "session":
                        continue
                    assert message["session_id"] == "test-session"
                    events.append(message["data"])
                    if message["data"]["type"] == "end":
                        break
                assert not [event for event in events if event["type"] == "error"]
                result = events[0]["data"]["message"]["json_object"]
                assert result["message_id"] == "test-message"
                assert result["idempotency_key"] == "test-send"
        finally:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
