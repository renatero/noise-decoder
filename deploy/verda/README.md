# Noise Decoder NVIDIA deployment

`nemotron.json` defines the Verda deployment `noise-decoder-nemotron`:

- Model: `nvidia/NVIDIA-Nemotron-Nano-9B-v2`, pinned Hugging Face revision.
- Engine: official `vllm/vllm-openai:v0.11.2`, pinned to its image digest.
- Compute: one L40S 48 GB, on demand; maximum one replica.
- Scaling: zero minimum replicas, queue-triggered startup, 300-second scale-down
  delay, 900-second request TTL. CPU/GPU utilization scaling is disabled.
- Model context: 16,384 tokens; four sequences; eager execution to reduce startup
  compilation. Mamba state uses float32 as NVIDIA recommends.
- No Hugging Face credential, persistent paid storage, or registry secret is needed
  for this public model and image. Verda's inference gateway requires the existing
  server-side inference API key.

Created on 2026-11-15 following explicit authorization to enable and publish.
Verda returned the endpoint:

`https://containers.datacrunch.io/noise-decoder-nemotron/v1`

The settings validator accepts both official container domains (`containers.verda.com`
and legacy `containers.datacrunch.io`), with an exact deployment path and HTTPS.
The Cloud API credentials are for deployment administration only; the dashboard
continues to use its separately stored inference API key.

## Cost and startup

Verda's authenticated `/v1/container-types` catalog quoted **USD 2.22 per running
hour** for one L40S on 2026-11-15. Startup and shutdown usage are billable. Verda's
current documentation describes minute-based usage, aggregated on bills in
10-minute intervals. Five minutes of idle delay is about USD 0.185 at that rate;
actual costs depend on startup time, requests, billing and future prices. There
is no always-running minimum replica and no paid storage attached by this manifest.

The initial image/model download can take several minutes. Subsequent cold starts
also require warming the model. The application submits each model-catalog request
and inference once using Verda's asynchronous gateway, then polls that request's
result. Each wait has a ten-minute deadline; HTTP calls have 45-second timeouts.
No second inference is automatically submitted. Polling URLs are restricted to
the same official host and deployment, and redirects are rejected.

## Reproduce or inspect

Use the official Cloud API with an OAuth token obtained from the operator's client
credentials. Check `GET /v1/container-deployments` before creating anything; do not
create duplicate deployments. Submit the manifest to `POST /v1/container-deployments`
only when a deployment with this name does not exist. Inspect these read endpoints:

- `/v1/container-deployments/noise-decoder-nemotron`
- `/v1/container-deployments/noise-decoder-nemotron/scaling`
- `/v1/container-deployments/noise-decoder-nemotron/replicas`
- `/v1/container-deployments/noise-decoder-nemotron/logs`
- `/v1/container-deployments/noise-decoder-nemotron/system-logs`

Do not put Cloud API tokens, inference keys or operator tokens in this repository.

## Sources checked 2026-11-15

- [Verda Cloud API](https://api.verda.com/v1/docs)
- [NVIDIA model and recommended runtime options](https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-9B-v2)
- [vLLM v0.11.2 Dockerfile: CUDA 12.9.1](https://github.com/vllm-project/vllm/blob/v0.11.2/docker/Dockerfile)
- [Verda R580 drivers and billing](https://docs.verda.com/containers/overview/)
- [Verda scaling](https://docs.verda.com/containers/scaling/)
- [Verda asynchronous inference](https://docs.verda.com/containers/synchronous-and-asynchronous-inference/)

NVIDIA's `/no_think` control is added for this model so evidence reviews request
direct structured output rather than spending the response budget on reasoning.
Model output still passes the application's exact-quotation and evidence-ID checks.
