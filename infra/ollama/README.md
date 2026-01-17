# Ollama service (Snow Day)

This folder provides a standalone Ollama container setup for this repo, mirroring the
“dedicated Ollama service” style in `snow_day/ollama/` (the reference repo you added),
but tailored for Snow Day and pinned to **Ollama 0.13.5**.

## Local dev (Docker Compose)

Snow Day’s root `docker-compose.yml` runs this as the `model` service.

```bash
docker compose up --build model
curl http://localhost:11434/api/tags
```

### Optional: pre-pull models on startup

In `docker-compose.yml`, set:

```yaml
environment:
  - OLLAMA_PULL_MODELS=phi3,llama3,gemma:2b
```

Models will still be cached to the `ollama_models` volume (`/root/.ollama`).

## Cloud Run (recommended shape)

Cloud Run can’t run multiple containers via Compose, so deploy **two services**:

- **ollama**: this container, exposes port `11434`
- **backend**: your FastAPI container, configured with `SNOWDAY_LLM_URL` pointing at the
  Ollama Cloud Run service URL

### Notes / gotchas

- **Model persistence**: Cloud Run instances are ephemeral. Without a persistent volume,
  Ollama will re-pull models on cold start. That can be slow and expensive.
- **Practical options**:
  - **Bake models into the image** (fast runtime, huge images; slower deploys).
  - **Use `OLLAMA_PULL_MODELS` at startup** (simple, but cold starts can be long).
  - **Move to GKE / Compute Engine** if you need persistent disks and predictable warm caches.

If you want to try Cloud Run anyway, start with CPU-only and small models (e.g. `phi3`,
`gemma:2b`) and budget for cold-start time.
