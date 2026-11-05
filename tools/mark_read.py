from dify_plugin import Tool

from linq_client import LinqClient, path_id


class MarkRead(Tool):
    def _invoke(self, tool_parameters):
        chat_id = path_id(tool_parameters.get("chat_id"))
        LinqClient(self.runtime.credentials.get("api_key")).request(
            "POST", f"/chats/{chat_id}/read"
        )
        yield self.create_json_message({"chat_id": chat_id, "status": "accepted"})
