from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from linq_client import LinqClient


class SendMessage(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        result = LinqClient(self.runtime.credentials.get("api_key")).send(tool_parameters)
        yield self.create_json_message(result)
        for key in (
            "chat_id",
            "message_id",
            "from_number",
            "idempotency_key",
            "status",
        ):
            yield self.create_variable_message(key, result[key])
