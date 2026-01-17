# syntax=docker/dockerfile:1
FROM ollama/ollama:0.13.5

# We use curl for readiness/health checks and for a predictable startup sequence.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Listen on all interfaces inside the container.
ENV OLLAMA_HOST=0.0.0.0:11434

EXPOSE 11434

COPY startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh

HEALTHCHECK --interval=10s --timeout=3s --retries=12 \
  CMD curl -fsS http://127.0.0.1:11434/api/tags >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/startup.sh"]
