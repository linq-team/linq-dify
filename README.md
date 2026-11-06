# Linq for Dify

Connect Dify agents and workflows to iMessage, RCS, and SMS through the Linq Partner API.
The integration has two installable plugins: **Linq** (outbound tools) and **Linq Trigger**
(signed inbound messages). Dify requires Tool and Trigger plugins to be separate packages.
Both are built from one source tree, with shared API code.

## Requirements

- Dify 1.17.1 or later, with plugin and trigger support; Python 3.12 for development.
- A Linq account, a provisioned line, and its Partner API key. Existing Linq usage charges apply;
  the plugin is free. See [Linq](https://linqapp.com) for account and service details.
- For automatic inbound setup, the key must be able to manage webhook subscriptions, and Dify's
  generated webhook address must be publicly reachable over HTTPS.

## Install and authorize

1. Install `linq-0.1.0.difypkg` from **Plugins → Install from Local Package File**, or install
   the reviewed Marketplace listing when available. Local unsigned packages may require your
   self-hosted administrator to allow unsigned plugins; use the reviewed package in production.
2. Open **Tools → Linq → Authorize**. Paste your Linq Partner API key, without `Bearer`.
3. Run **List phone numbers** to check which lines the key can access.
4. Add Linq tools to a Workflow or Agent. Linq chooses the messaging service supported by the
   line/conversation; this plugin does not let an agent force iMessage instead of RCS or SMS.

## Tools

| Tool | Inputs | Result |
| --- | --- | --- |
| Send message | `text`, `idempotency_key`, plus `chat_id` **or** `to` with optional `from_number` | Message/chat IDs, idempotency key, acceptance status, API result |
| List phone numbers | None | Accessible lines |
| Get chat | `chat_id` | Chat details |
| List messages | `chat_id`, optional `limit` (1–100) and `cursor` | Messages and `next_cursor` |
| Mark chat read | `chat_id` | Acceptance status |
| Set typing indicator | `chat_id`, `action` (`start` or `stop`) | Acceptance status |

`to` is a comma-separated list of 1–31 E.164 phone numbers or email addresses.
`from_number` must be a Linq line in E.164 format. Do not combine `chat_id` with either field.
An explicitly selected sender uses Linq's create-chat endpoint: its first message cannot contain
a link. The automatic sender endpoint supports a link in the first message. Respect Linq's
channel, account, opt-out, and messaging restrictions. Typing is intended for direct chats.

Send returns **accepted**, not delivered. Check later message state with List messages;
this version does not expose delivery-status triggers.

### Safe retries

Supply a unique, stable `idempotency_key` for each logical message. Repeat that same key only
when retrying the same message. For replies, use the inbound trigger's `reply_idempotency_key`.
For multiple replies to one incoming message, append a stable suffix (`:1`, `:2`, etc.).
For outbound campaigns or scheduled workflows, derive the key from a durable job/event ID.
Do not generate a different random key on every workflow retry.

The client retries transient failures twice (including HTTP 409/error 2009 while a chat is
being created) with the same request body and key, uses a 10-second
timeout per HTTP operation, and respects Retry-After up to five seconds. Longer waits return an
error so the workflow can retry later. Error messages do not expose response bodies, credentials,
or message content. A successful HTTP response without the required send identifiers is treated
as an unknown result, not acceptance; retry it with the same key. Changing the API host,
following redirects, and disabling TLS verification
are not supported.

## Receive messages and reply

1. Install `linq_trigger-0.1.0.difypkg` and create a Workflow with the **Linq → Message received** trigger.
2. Create a subscription using a Linq API key. Optionally enter comma-separated Linq line numbers
   to restrict it. Empty means every line accessible to this key.
3. Dify creates a Linq `message.received` subscription and stores the returned signing secret.
   Its callback URL includes `version=2026-02-03` to request the correct Linq payload.
4. Connect the trigger to an LLM node. Pass `text` as the incoming message. Set an appropriate
   system prompt for your assistant. Media-only messages have empty `text`; branch on empty text
   rather than sending it blindly to the LLM. `parts` contains the original parts, but this plugin
   does not download media.
5. Connect the LLM to **Linq → Send message**, mapping:

   | Send input | Workflow value |
   | --- | --- |
   | `chat_id` | Trigger → `chat_id` |
   | `text` | LLM → `text` |
   | `idempotency_key` | Trigger → `reply_idempotency_key` |
   | `to`, `from_number` | Leave empty |

6. Test with a dedicated Linq test line and a recipient who agreed to receive test messages.
   Publish the workflow after verifying one inbound message produces one intended reply.

Trigger outputs: `event_id`, `message_id`, `chat_id`, `sender`, `line`, `text`, `service`,
`is_group`, `sent_at`, `parts`, and `reply_idempotency_key`. Group messages retain their chat ID;
an automated reply goes to that group. Add a condition on `is_group` if replies should be DM-only.

The trigger validates the raw request's Standard Webhooks HMAC and rejects timestamps more than
five minutes in the past or future. It ignores outbound/self-sent, reconciled, and zero-retention
messages. Unsupported old message payloads fail with an instruction to select the correct version.
Removing an automatically created Dify subscription deletes its Linq webhook subscription.

For manual setup, create the Linq webhook yourself targeting Dify's endpoint with
`?version=2026-02-03` (or `&version=2026-02-03` if a query already exists), subscribe only to
`message.received`, and enter its `whsec_` signing secret in Dify. Manually created subscriptions
must be removed in Linq yourself. If automatic creation times out, check Linq for a created
subscription before retrying: create calls are not retried automatically to avoid orphan duplicates.

## Data and limitations

- This version sends **text only**. Inbound media metadata is passed through, not downloaded.
- Dify and configured model providers can retain workflow inputs, outputs, and logs. This is not
  a zero-retention integration. The trigger intentionally skips messages marked `zero_retention`.
- The plugin creates no database tables or message logs and requests no Dify storage permission.
  Dify itself stores provider credentials, subscriptions, and workflow records.
- Webhooks may be delivered more than once. The trigger is stateless: workflow executions are
  not deduplicated. Linq's stable message key prevents duplicate outbound replies, but other nodes
  with side effects must implement their own deduplication.
- Authentication is bring-your-own-key. Account/line provisioning, WhatsApp, voice calls,
  attachments, delivery triggers, and conversation memory management are outside this version.

See [PRIVACY.md](PRIVACY.md) for the data flow and privacy responsibilities.

## Development

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
ruff format --check .
```

For Dify remote debugging, configure the environment variables provided by Dify's plugin debugger
(`INSTALL_METHOD=remote`, `REMOTE_INSTALL_HOST`, `REMOTE_INSTALL_PORT`, `REMOTE_INSTALL_KEY`)
locally, then run `python main.py`. Never commit credentials or debugger keys.

Build both packages with the [Dify CLI](https://github.com/langgenius/dify-plugin-daemon).
Use a new output directory on each build (the command does not overwrite existing artifacts):

```sh
python scripts/package.py --cli /path/to/dify --output ./dist/review-1
```

The build stages only each plugin's runtime files, adds its own manifest, and packages each
independently. The root source tree is not itself an installable plugin. Manifests live in
`manifests/`; shared client code is copied into both artifacts by the build script.

Tests use synthetic data and mocked API responses; they do not send real messages. See
[VALIDATION.md](VALIDATION.md) for what has and has not been verified for this release.

Source and support: [linq-team/linq-dify](https://github.com/linq-team/linq-dify).
API contract: [Linq Partner API](https://docs.linqapp.com/channel/imessage/).
Implementation reference: [Linq Convex component](https://github.com/linq-team/linq-convex).
Licensed under Apache-2.0. Linq logo sourced from Linq's website repository.
