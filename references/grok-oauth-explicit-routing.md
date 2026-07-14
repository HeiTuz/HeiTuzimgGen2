# Explicit Grok OAuth Route

## Activation

The Grok route is opt-in. Select it only when the user's current request explicitly asks to generate or edit an image with `Grok`, `그록`, or `xAI`. A bare image request, an exact-count request, or the mere presence of xAI credentials never selects Grok; those requests stay on the default Codex subscription route.

Before every Grok execution, require both:

1. at least one configured Hermes `xai-oauth` credential; and
2. the Hermes-native xAI `image_generate` tool to be available in the current session.

An `XAI_API_KEY` by itself does not enable this HeiTuz route. Never inspect or print token files, initiate login, use `hermes chat` subprocesses, start `progrok`, reuse browser cookies, or call a private endpoint. If either gate is missing, return `grok_route: disabled` with the missing capability and stop. Never fall back to Codex, Higgsfield, an API key, or another model/provider.

Tool availability is session-scoped. After enabling or configuring Hermes image generation, start a fresh Hermes session before treating `image_generate` as available.

## Single image

1. Compile the final IMAGE prompt through the ordinary HeiTuzMPW boundary when available.
2. Record `requested_provider: grok`, `auth_mode: xai-oauth`, and the requested geometry. Never record credential values.
3. Invoke the native `image_generate` tool once with the xAI-backed model selected by Hermes configuration.
4. Materialize the returned image locally immediately; remote result URLs are not durable delivery evidence.
5. Record the local path, byte size, SHA-256, provider/model provenance returned by the tool, request/job identifier when present, and `qc_status: not_evaluated`.
6. Run the same independent visual QC used by the Codex lane. Transport success is not visual acceptance.

## Exact-N batch

An explicit request for N Grok images creates exactly N independent jobs. Never reduce N to the worker limit and never submit all N simultaneously.

- Build an immutable manifest with stable job IDs and one complete prompt per job.
- Submit the first job as a transport-and-quality pilot. Do not fan out until its artifact is locally materialized, hash-verified, and independently approved.
- Start bounded fan-out with 3 active jobs. After healthy completions, grow to at most 5. The remaining jobs stay queued.
- Every job owns an independent output path and ledger record: `queued`, `running`, `succeeded`, or `failed`; attempt count; prompt/manifest digest; output size/hash; non-secret error class; provider/model provenance; and QC state.
- On rate limiting, freeze growth, honor `Retry-After` when present, and reduce active concurrency. Retry only failed jobs under a fresh attempt record; never restart successful jobs or overwrite their artifacts.
- Retry transient timeout/429/5xx failures only within the bounded retry budget. Authentication, entitlement, malformed-request, or unavailable-tool failures stop without provider fallback.
- Completion means all requested jobs are terminal and every success is hash-verified. Partial success remains partial; it is not rounded up to N.

## Routing examples

| Request | Route |
| --- | --- |
| “이미지 한 장 만들어줘” | Codex subscription default |
| “20장 만들어줘” | Codex exact-N default |
| “Grok으로 한 장 만들어줘” | Grok OAuth, if both gates pass |
| “그록으로 20장 생성해줘” | Grok OAuth exact-N queue, if both gates pass |
| “xAI 느낌으로 만들어줘” where xAI is only an aesthetic phrase | Codex; provider intent is not explicit |
| Explicit Grok request without `xai-oauth` | Disabled; no fallback |
| Explicit Grok request with only `XAI_API_KEY` | Disabled; API-key-only does not enable this route |

## Secret-safe evidence

Allowed durable facts: credential type (`xai-oauth`), credential availability boolean, provider/model names returned by the tool, request/job IDs, usage facts, output metadata, hashes, and classified errors.

Forbidden durable data: access/refresh tokens, API keys, cookies, authorization headers, raw auth files, or raw exception bodies that may contain them.
