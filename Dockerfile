FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS builder
WORKDIR /build
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.lock

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 1001 agent && useradd --uid 1001 --gid agent --create-home agent
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=1001:1001 src ./src
COPY --chown=1001:1001 data/profile.json ./data/profile.json
RUN mkdir -p /app/data/state && chown -R 1001:1001 /app/data
ENV PYTHONPATH=/app/src
USER 1001:1001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]
CMD ["uvicorn", "agent_cv.app:factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers", "--limit-concurrency", "32", "--timeout-keep-alive", "5"]
