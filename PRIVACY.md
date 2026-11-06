# Linq for Dify — privacy

This plugin sends and receives messaging data through the Linq Partner API. It is not a
zero-retention integration.

## Data processed and where it goes

- **Linq API key:** entered in Dify's secret credential field, stored by Dify, and sent only to
  `https://api.linqapp.com` in the Authorization header. It is never included in tool outputs.
- **Message text and recipient identifiers:** sent to Linq to deliver requested messages. Phone
  numbers, email addresses, chat/message IDs, line identifiers, delivery metadata, and message
  content returned by Linq are passed back to the Dify workflow or agent.
- **Inbound webhooks:** the signature is verified before message content is parsed. The incoming
  message's text, sender, line, chat/message/event IDs, service, timestamp, group flag, and message
  parts are passed to Dify. Parts can include media URLs and other identifying information.
  This plugin does not download those URLs. Reconciled messages and messages marked zero-retention
  are not passed to workflows.
  Dify uses the sender's phone number or email as the trigger's end-user identifier and can
  retain associated end-user records.
- **Webhook subscription:** creating a trigger sends Dify's public callback URL and optional line
  filters to Linq. The signing secret and subscription ID returned by Linq are stored in Dify's
  subscription settings. Deleting an automatically managed subscription requests its removal
  from Linq.

No data is sent to plugin-author telemetry, analytics, or any additional service by this code.
The plugin does not create its own persistent store or log message content. Dify can retain
credentials, webhook configuration, workflow inputs/outputs, and execution records. A workflow
can send content to its selected model provider or other nodes; these destinations are controlled
by the workflow owner and are not limited by this plugin.

## Retention, access, and deletion

Retention is governed by the user's Linq account, Dify deployment, chosen model providers, and
workflow configuration. Do not use this plugin for a zero-retention requirement. Configure
retention and access controls in those services. Remove credentials and subscriptions in Dify,
delete manually created subscriptions in Linq, and request data deletion from the service that
holds the data. Removing the plugin does not automatically delete historical workflow records
or messages already delivered to recipients.

Use messaging data only for authorized purposes and ensure recipients have agreed to the
applicable use. The plugin does not determine consent or provide a legal basis for processing.

Service policies: [Linq privacy](https://linqapp.com/policies/privacy-policy),
[Dify privacy](https://dify.ai/legal/privacy-policy). Consult the policies of every model provider and other
service connected to the workflow. Support: [Linq plugin issues](https://github.com/linq-team/linq-dify/issues).
