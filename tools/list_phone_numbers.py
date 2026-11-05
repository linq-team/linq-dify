from dify_plugin import Tool

from linq_client import LinqClient


class ListPhoneNumbers(Tool):
    def _invoke(self, tool_parameters):
        yield self.create_json_message(
            LinqClient(self.runtime.credentials.get("api_key")).request("GET", "/phone_numbers")
        )
