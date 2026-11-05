from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from linq_client import LinqClient, LinqError


class LinqProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            LinqClient(credentials.get("api_key")).request("GET", "/phone_numbers")
        except LinqError as error:
            raise ToolProviderCredentialValidationError(str(error)) from None
