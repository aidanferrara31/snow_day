#!/bin/sh
set -eu

# Default to the standard Ollama port unless overridden.
export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}"

STARTUP_TIMEOUT_SEC="${OLLAMA_STARTUP_TIMEOUT_SEC:-60}"

echo "[ollama] starting server (OLLAMA_HOST=${OLLAMA_HOST})"
ollama serve &
OLLAMA_PID="$!"

echo "[ollama] waiting for API to become ready..."
i=1
while [ "$i" -le "$STARTUP_TIMEOUT_SEC" ]; do
  if curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "[ollama] ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$i" -gt "$STARTUP_TIMEOUT_SEC" ]; then
  echo "[ollama] ERROR: API did not become ready within ${STARTUP_TIMEOUT_SEC}s" >&2
  kill "$OLLAMA_PID" >/dev/null 2>&1 || true
  exit 1
fi

# Optional: pre-pull models on container start. This is useful when deploying to an
# environment with an ephemeral filesystem (e.g., Cloud Run) where you want the
# container to warm its model cache at boot.
#
# Examples:
#   OLLAMA_PULL_MODELS="phi3"
#   OLLAMA_PULL_MODELS="phi3,llama3,gemma:2b"
if [ -n "${OLLAMA_PULL_MODELS:-}" ]; then
  MODELS="$(printf "%s" "$OLLAMA_PULL_MODELS" | tr ',' ' ')"
  echo "[ollama] pre-pulling models: ${MODELS}"
  for model in $MODELS; do
    if [ -n "$model" ]; then
      echo "[ollama] pulling: ${model}"
      ollama pull "$model"
    fi
  done
else
  echo "[ollama] OLLAMA_PULL_MODELS not set; skipping pre-pull"
fi

echo "[ollama] server running (pid=${OLLAMA_PID})"
wait "$OLLAMA_PID"
