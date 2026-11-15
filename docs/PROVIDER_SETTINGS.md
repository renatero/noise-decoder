# Provider settings and experimental company research

The dashboard gear opens **Provider settings**. Context.dev, Cala.ai, Featherless,
and Verda credentials are stored on the server. API responses expose only whether
a key is configured, never the key itself. An empty key field preserves the saved
key; **Remove saved key** explicitly removes it, including an environment fallback.
Saving settings takes effect immediately, including the Context.dev source menu.

## Operator access

Settings edits and all experimental requests require the server's operator token.
Public collection and coordination analysis retain their existing access rules.
Use HTTPS, or an SSH tunnel to localhost. The browser holds the operator token
only in page memory; lock or reload the page to remove it. It is never placed in
localStorage, URLs, or cookies. There is no public token creation/reset endpoint.

The deployment service sets `NOISE_STATE_DIR=/var/lib/noise-decoder/settings`.
Initialize the token if needed (this prints its path, not its value):

```sh
cd /opt/projects/noise-decoder
sudo -u ubuntu env NOISE_STATE_DIR=/var/lib/noise-decoder/settings \
  .venv/bin/python -m src.providers.settings
```

Read the token privately over SSH and paste it into the settings unlock field:

```sh
sudo cat /var/lib/noise-decoder/settings/operator-token
```

The private directory has mode 0700. The token and settings SQLite database have
mode 0600, owned by the service user. Keys are stored as plaintext in this private
database, not encrypted with a separate vault key. Protect server access and
backups accordingly. Local development uses the git-ignored `.noise-state/`.
Environment keys (`CONTEXT_API_KEY`, `CALA_API_KEY`, `FEATHERLESS_API_KEY`,
`VERDA_API_KEY`) remain defaults until overridden by saved settings.
To revoke an operator token, replace its file with a new random value securely;
existing page tokens stop authorizing requests immediately.

## Providers

- **Context.dev**: existing bounded news collector, now configurable from the UI.
  Keys, enable/disable status and key rotation apply without restarting. Its
  existing cache, four requests/minute and default 20 requests/day limits remain.
- **Cala.ai**: explicit background research through `POST /v1/knowledge/search`,
  `X-API-KEY` authentication, and an `input` field. Generated text and supplied
  reference IDs are displayed as unverified leads. Opaque reference IDs are not
  represented as original-source links. No documented cost-free key-check endpoint
  is assumed; a research query validates access while using the account quota.
- **Featherless**: `GET /v1/plan` checks authenticated API access; a plan-filtered
  model catalog checks the selected model. Reviews use `/v1/chat/completions`.
  The initial model is `Qwen/Qwen2.5-7B-Instruct`; availability is checked before
  every review. The UI accepts another exact model ID from the provider catalog.
- **Verda**: uses `/v1/models` and `/v1/chat/completions`. Only catalog entries with
  an `nvidia/` model namespace or `owned_by: nvidia` are accepted. GPU vendor alone
  does not qualify. The configured model must exist in the endpoint's catalog;
  there is no fallback to other models. For a custom vLLM deployment, retain the
  original NVIDIA model ID when serving it; an arbitrary local alias cannot prove
  the publisher. The operator remains responsible for which weights are deployed.

Verda's managed catalog, checked **2026-11-15**, lists Kimi and DeepSeek rather than
an NVIDIA model. The settings support an **existing** Verda NVIDIA vLLM deployment
at `https://containers.verda.com/DEPLOYMENT/v1`, with its inference API key. The
application does not create GPU resources, add funds, or enable paid deployments.
Only that host/path pattern and `https://inference.verda.com/v1` are accepted; other
provider endpoints are fixed. Redirects are never followed with credentials.

Experimental features default off. Operators can explicitly enable each provider.
The supplied Featherless credential was accepted by `/v1/plan` on 2026-11-15; the
same supplied credential was rejected by Verda's managed `/v1/models` (HTTP 401).
No Cala credential was supplied. Credentials themselves are never committed.

## Review behavior and limits

Use **Experimental company research** below the investigation report. Enter an
exact company/entity name, choose a provider, and run the review. Cala does its
own background research. Featherless and Verda inspect up to 20 collected records,
with at most 2,000 characters of text per record. They do not independently search
the web. Only the selected provider receives that request. The UI states the data
transfer and potential credit cost before execution.

Company relevance, namesakes, ownership, government funding, political links,
state-media ownership, and documented influence activity are possible subjects.
Nationality and political association alone are not grounds for propaganda claims.
Model output is provisional, separate from the coordination verdict, and never
changes its score or graph. Claims without a matching record and exact quotation
are omitted. Quote validation is not fact-checking: humans still need to assess
source reliability, attribution and whether the quote supports the claim.
Synthetic investigation input retains its synthetic label. Research can be exported
separately as JSON with provider, model, time, entity, findings and citations.

Each experimental provider is limited to four operations per minute and 20 per UTC
day, durably recorded in SQLite. Cala is additionally capped at 90 operations per
rolling 30 days. An operation may include a model catalog check plus inference;
these are application limits, not advertised vendor quotas or spending guarantees.
Access tests and failed/uncertain requests consume an operation. There are no
automatic retries. Inference is capped at 1,800 output tokens, responses at 2 MiB,
and HTTP timeouts at 45 seconds. Provider errors are sanitized before display.

## Official documentation verified 2026-11-15

- [Cala search](https://docs.cala.ai/api-reference/search)
- [Featherless quickstart](https://featherless.ai/docs/quickstart-guide)
- [Featherless plan endpoint](https://featherless.ai/docs/api-reference-plan)
- [Featherless model catalog](https://featherless.ai/docs/api-reference-models)
- [Verda managed models](https://docs.verda.com/inference/models/)
- [Verda inference quickstart](https://docs.verda.com/inference/quickstart/)
- [Verda vLLM deployment endpoints](https://docs.verda.com/containers/tutorials/deploy-with-vllm-indepth/)

## Validation

`src/api/tests/test_providers.py` covers authorization, origin/HTTPS checks, secret
redaction, persistence/removal, live Context configuration, endpoint restrictions,
NVIDIA-only selection, citation validation, Cala payloads, durable failure budgets,
and sanitized provider errors. Run it with:

```sh
.venv/bin/python -m unittest src.api.tests.test_providers
```

`src/web/tests/providers.cjs` exercises settings, secret handling, review requests,
synthetic attribution, safe rendering, export and mobile layout in Playwright.
Provider requests in this browser test are mocked and spend no credits.
