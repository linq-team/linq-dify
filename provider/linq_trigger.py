from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dify_plugin.entities.trigger import EventDispatch, Subscription, UnsubscribeResult
from dify_plugin.errors.trigger import (
    SubscriptionError,
    TriggerProviderCredentialValidationError,
)
from dify_plugin.interfaces.trigger import Trigger, TriggerSubscriptionConstructor
from werkzeug import Response

from linq_client import LinqClient, LinqError, path_id, phone_number
from webhooks import inbound_message, verify_request


class LinqTrigger(Trigger):
    def _dispatch_event(self, subscription, request):
        event = verify_request(request, subscription.properties.get("signing_secret", ""))
        message = inbound_message(event)
        return EventDispatch(
            events=["message_received"] if message else [],
            user_id=message["sender"] if message else "",
            response=Response(status=200),
            payload=message or {},
        )


class LinqSubscriptionConstructor(TriggerSubscriptionConstructor):
    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        try:
            LinqClient(credentials.get("api_key")).request("GET", "/phone_numbers")
        except LinqError as error:
            raise TriggerProviderCredentialValidationError(str(error)) from None

    def _create_subscription(self, endpoint, parameters, credentials, credential_type):
        try:
            url = urlsplit(endpoint)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.fragment
            ):
                raise LinqError("Dify must provide a public HTTPS webhook endpoint.")
            query = [
                (k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k != "version"
            ]
            target = urlunsplit(url._replace(query=urlencode(query + [("version", "2026-02-03")])))
            body = {"target_url": target, "subscribed_events": ["message.received"]}
            numbers = parameters.get("phone_numbers")
            if numbers:
                body["phone_numbers"] = [phone_number(n.strip()) for n in numbers.split(",")]
            client = LinqClient(credentials.get("api_key"))
            # Creation is not idempotent: never automatically retry after a timeout.
            created = client.request("POST", "/webhook-subscriptions", body=body, retry=False)
            if not isinstance(created.get("id"), str) or not isinstance(
                created.get("signing_secret"), str
            ):
                raise LinqError(
                    "Linq returned an incomplete subscription. Check subscriptions in Linq before retrying."
                )
            return Subscription(
                endpoint=endpoint,
                parameters=parameters,
                properties={
                    "subscription_id": created["id"],
                    "signing_secret": created["signing_secret"],
                },
            )
        except LinqError as error:
            raise SubscriptionError(str(error), error_code="LINQ_SUBSCRIPTION_FAILED") from None

    def _delete_subscription(self, subscription, credentials, credential_type):
        subscription_id = subscription.properties.get("subscription_id")
        if not subscription_id:
            return UnsubscribeResult(
                success=True,
                message="Manually configured subscription: remove it in Linq.",
            )
        try:
            LinqClient(credentials.get("api_key")).request(
                "DELETE",
                f"/webhook-subscriptions/{path_id(subscription_id, 'subscription_id')}",
            )
        except LinqError as error:
            if error.status != 404:
                return UnsubscribeResult(success=False, message=str(error))
        return UnsubscribeResult(success=True, message="Linq webhook subscription removed.")

    def _refresh_subscription(self, subscription, credentials, credential_type):
        return subscription
