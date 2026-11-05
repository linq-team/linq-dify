from dify_plugin import Tool

from linq_client import LinqClient, LinqError, path_id


class SetTyping(Tool):
    def _invoke(self, tool_parameters):
        chat_id = path_id(tool_parameters.get("chat_id"))
        action = tool_parameters.get("action")
        if action not in ("start", "stop"):
            raise LinqError("action must be start or stop.")
        LinqClient(self.runtime.credentials.get("api_key")).request(
            "POST" if action == "start" else "DELETE", f"/chats/{chat_id}/typing"
        )
        yield self.create_json_message({"chat_id": chat_id, "action": action, "status": "accepted"})
