# Plugin Submission

Prepared review draft. Make the source public before submitting. Runtime coverage and external-test limitations are recorded below.

## Plugin information

- **Author**: linq-team
- **Plugin name**: linq
- **Version**: 0.1.0
- **Source repository**: https://github.com/linq-team/linq-dify
- **Contact**: support@linqapp.com

## Submission type

- [x] New plugin
- [ ] Version update

## What changed

Adds Linq Partner API v3 tools for sending text, reading chats/messages, listing lines,
marking chats read, and controlling typing indicators. Stable send idempotency keys support
retry-safe replies over iMessage, RCS, and SMS. The separate Linq Trigger package supplies
inbound workflow events because Dify does not permit tools and triggers in one package.

## Risk level

- [ ] Low risk
- [x] Medium risk
- [ ] High risk

## Required checks

- [x] I have read and followed the [Marketplace submission requirements](https://github.com/langgenius/dify-plugins/blob/main/docs/plugin-submission-requirements.md).
- [x] I have read and comply with the [Plugin Development Guidelines](https://docs.dify.ai/en/develop-plugin/publishing/standards/contributor-covenant-code-of-conduct).
- [x] I tested this plugin on Dify Community Edition and Dify Cloud, or documented any limitation below.
- [x] The package contains only files needed at runtime.
- [x] The package does not contain secrets, local credentials, `.env` files, `.git` directories, virtual environments, caches, logs, or IDE files.
- [x] The package does not contain executables or bundled binaries, or I explained why they are required below.
- [x] The plugin README includes setup steps, usage instructions, required APIs or credentials, connection requirements, and the source repository link.
- [x] The plugin includes `PRIVACY.md` or a hosted privacy policy, and `manifest.yaml` references it.
- [x] All user-facing text is primarily in English, with any localized README files following the [i18n guidance](https://docs.dify.ai/en/develop-plugin/features-and-specs/plugin-types/multilingual-readme).

## Security and privacy notes

The plugin performs authenticated third-party API write actions and transmits personal data:
phone numbers, email handles, message text, chat/message identifiers, and message metadata.
The only outbound network destination is the fixed HTTPS origin api.linqapp.com. It has no
user-configurable API host, proxy, SQL, SSH, shell, code execution, filesystem access, or browser
automation. It does not download user-supplied URLs. Returned media URLs are data only.
The Dify-generated HTTPS callback URL is registered with Linq for webhook delivery; the plugin
does not fetch it. API calls have timeouts; send retries reuse the same idempotency key.
Errors omit response bodies and credentials. Webhooks use raw-body HMAC verification,
constant-time comparison, and a five-minute timestamp window. Outbound/self-sent, reconciled,
and zero-retention messages do not trigger workflows. The plugin does not create persistent
message storage; Dify and downstream model providers may retain workflow data, so it is not
a zero-retention integration. The plugin is intended for ordinary messaging; workflows handling
sensitive personal data require reassessment of this risk classification before submission.

## Local validation

See VALIDATION.md for the exact checks and results. Unit/SDK tests use synthetic messages and
mocked HTTP. The package is built with Dify CLI 0.6.15 and checked with the Marketplace Toolkit.

## Reviewer notes

- Both packages were installed in local Dify Community Edition 1.17.1. A signed synthetic
  event ran the trigger-to-reply workflow; credential validation, masked secrets, HTTP error
  mapping, and subscription deletion passed against an isolated TLS mock. Dify Cloud and
  real Linq send/receive remain untested. Use a dedicated test line before production use.
- The source repository is private during internal review; make it public before Marketplace submission.
- Submit exactly one package per PR. This PR is for linq-0.1.0.difypkg.
- Text-only sending in v0.1.0; no account provisioning, outbound attachments, delivery-status triggers,
  or conversation-memory management.
- The financial-activity scanner flags README disclosure of Linq service usage costs. This plugin
  does not create payments, purchase credits, manage billing, or transfer assets.
- Webhook executions are at-least-once. Stable send keys prevent duplicate replies; other workflow
  side effects need their own deduplication.
