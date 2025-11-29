# Snow Day

Snow Day scrapes ski resort condition data, normalizes key metrics, and scores
resorts so trip planners can quickly decide where to ride next.

## Containerized setup

Build and run the full stack with Docker Compose:

```bash
make bootstrap  # builds images and installs frontend dependencies
make dev        # starts backend (FastAPI), frontend (Vite), and the local model
```

Or start everything directly with Compose:

```bash
docker-compose up --build
```

Service ports:

- API/backend: http://localhost:8000
- Frontend: http://localhost:5173
- Local model (Ollama-compatible): http://localhost:11434

Data persistence and caching:

- `snow_day_data` volume stores the SQLite database at `/app/data/conditions.db`.
- `ollama_models` volume caches pulled models at `/root/.ollama`.

Trigger a manual scrape/score refresh against a running stack:

```bash
make refresh
```

## API and frontend

Start the FastAPI server with:

```bash
uvicorn snow_day.api:app --reload
```

Endpoints:

- `GET /conditions` returns the latest normalized snapshots for each resort.
- `GET /rankings` provides ranked resorts with scoring rationales and an LLM summary.
- `POST /refresh` re-scrapes all resorts and returns fresh rankings.

The `frontend` folder contains a Vite + React + Tailwind UI that calls these endpoints
for a live dashboard. Set `VITE_API_URL` to the API base URL when running `npm run dev`.

## Local LLM model server

Use the provided Dockerfile to run an Ollama-compatible model server locally.
This keeps model evaluation self-contained while allowing you to choose the
model family that fits your hardware (e.g., `phi3`, `llama3`, or `gemma`).

1. Build the image:
   ```bash
   docker build -f Dockerfile.ollama -t snow-day-ollama .
   ```
2. Start the server:
   ```bash
   docker run -d --name snow-day-ollama -p 11434:11434 snow-day-ollama
   ```
3. Pull a model (run after the container is up):
   ```bash
   docker exec snow-day-ollama ollama pull phi3
   # or choose alternatives
   docker exec snow-day-ollama ollama pull llama3
   docker exec snow-day-ollama ollama pull gemma:2b
   ```
4. Verify the server is healthy:
   ```bash
   curl http://localhost:11434/api/tags
   ```

The Dockerfile intentionally avoids downloading models during build so it can be
built offline; fetching models happens after the container starts. Replace
`phi3` with any other available Ollama tag as desired.

## LLM client wrapper

`snow_day.services.llm_client` provides a thin client for the local model server
with timeout handling and a rule-based fallback. Construct `ScoredResort`
objects from scoring results and pass them to the client to generate summaries
or a daily recommendation:

```python
from snow_day.services import LLMClient, ScoredResort
from snow_day.services.scoring import ScoreResult

result = ScoreResult(score=92.0, rationale="Fresh powder and calm winds")
resorts = [ScoredResort.from_result("Alpine Ridge", result)]

client = LLMClient(model="phi3", base_url="http://localhost:11434", timeout=8)
print(client.summarize_top_resorts(resorts, top_n=3))
print(client.daily_recommendation(resorts))
```

If the LLM request fails or times out, the client falls back to deterministic
text based on the scoring rationales so downstream consumers always receive
usable output.
