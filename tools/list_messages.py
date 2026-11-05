from dify_plugin import Tool

from linq_client import LinqClient, page_parameters, path_id


class ListMessages(Tool):
    def _invoke(self, tool_parameters):
        chat_id = path_id(tool_parameters.get("chat_id"))
        yield self.create_json_message(
            LinqClient(self.runtime.credentials.get("api_key")).request(
                "GET",
                f"/chats/{chat_id}/messages",
                params=page_parameters(tool_parameters),
            )
        )
