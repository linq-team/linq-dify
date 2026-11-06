# Validation — 0.1.0 review build

Verified on November 6, 2026 using Python 3.12.16, Dify Plugin SDK 0.11.0, and Dify CLI 0.6.15.
These are internal review packages, not Marketplace-approved releases.

## Verified

- `python -m pytest -q`: **83 passed**. Includes all six tools through the Dify SDK,
  send routing and response IDs, unchanged idempotency keys across retries, HTTP error redaction,
  timeouts, provisioning-conflict retries, malformed-send rejection, pagination/input validation,
  signature rejection, timestamp checks, inbound filtering,
  subscription creation/deletion, and separate Tool/Trigger registration.
- Fresh Python processes start both staged plugins. The Tool process accepts a real Dify
  protocol request and returns a successful synthetic send plus its output variables. HTTP is
  mocked in this test; no real messages are sent.
- `ruff check .` and `ruff format --check .`: passed.
- CI also builds and uploads both packages with a checksum-pinned Dify CLI.
- Both packages build with the Dify CLI, with tools and triggers separated as required by the
  daemon's `PluginDeclaration.ManifestValidate` in version 0.6.15.
- Marketplace Toolkit checks: **zero blocking failures for each package**, including package
  contents, secrets, binaries, manifest/README metadata, dependencies, Python compilation,
  and sensitive-capability disclosure.
- The dependency scan reports no known vulnerabilities in the **two directly pinned runtime
  dependencies**. This is not a claim that every possible transitive dependency is vulnerability-free.

## Reproduce

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
ruff format --check .
python scripts/package.py --cli /path/to/dify --output ./dist/review-1
python /path/to/dify-marketplace-toolkit/validator/validate-difypkg.py \
  ./dist/review-1/linq-0.1.0.difypkg \
  --pr-body-file ./SUBMISSION.md --output-dir ./validation-report/linq
python /path/to/dify-marketplace-toolkit/validator/validate-difypkg.py \
  ./dist/review-1/linq_trigger-0.1.0.difypkg \
  --pr-body-file ./SUBMISSION_TRIGGER.md --output-dir ./validation-report/linq_trigger
```

The Marketplace Toolkit requires its `yq` dependency. This build used toolkit commit
`57a21d1304b1108df3e6b90a15a4f5dd9f0915f9`.

## Review notes

- The financial-activity heuristic flags the README's disclosure of Linq service usage costs.
  Neither plugin performs payments, purchases, billing changes, or asset transfers.
- Access-domain and dependency reports are informational: `api.linqapp.com` is the declared
  outbound host and runtime dependencies are pinned.
- Pytest reports upstream SDK warnings for gevent import order in the test process and a
  Pydantic deprecation. The fresh plugin process initializes the SDK before HTTP clients.
- A real local Dify Community Edition 1.17.1 deployment (plugin daemon 0.6.10-local)
  installed both packaged plugins through its package-upload API. It validated credentials,
  created a managed subscription, masked its API key and signing secret in the subscription
  API, and deleted the upstream subscription on removal. A signed synthetic inbound event
  returned HTTP 200 and ran a published trigger-to-send workflow, producing exactly one
  reply request in the incoming chat with key `dify-reply:runtime-msg-2`. Invalid signatures
  and old payload versions returned HTTP 400. The fixed Linq hostname resolved to an
  isolated TLS mock with a trusted test CA; no real message was sent. This exercised the
  Dify runtime, persistence, queue, and plugin processes, rather than replacing SDK calls.
- The API contract was checked against Linq's published v3 OpenAPI and the Convex component at
  commit `9d1ef531e2950afd7521912c0747a16fb1addcce`.

## Not yet verified

Dify Cloud, browser-driven setup, real Linq credentials, real outbound delivery, and external
inbound webhook delivery have not been exercised. Complete the README's test workflow on a
dedicated line before production use. The local Community runtime smoke above used synthetic
traffic and does not prove external Linq connectivity or real delivery. Source visibility, Marketplace duplicate-version checks, upstream PR metadata,
and Dify's human review remain release steps.

The source repository remains private during internal review. Each Marketplace submission
must contain just one of the two packages and link to publicly accessible source.
