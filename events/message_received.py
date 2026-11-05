from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class MessageReceived(Event):
    def _on_event(self, request, parameters, payload):
        return Variables(variables=payload)
