FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 GRADIO_ANALYTICS_ENABLED=False GUARDIAN_CONTAINER=1
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt package.json package-lock.json ./
RUN pip install --no-cache-dir -r requirements.txt && npm ci --registry=https://registry.npmjs.org && npx playwright install --with-deps chromium
COPY guardian guardian
COPY investigator investigator
COPY demo demo
COPY scripts scripts
COPY observability observability
COPY tests tests
RUN mkdir -p /app/.runtime/investigator /app/.runtime/phoenix && useradd --uid 10001 --create-home investigator && chown -R investigator /app
USER investigator
ENV PHOENIX_WORKING_DIR=/app/.runtime/phoenix
CMD ["python","scripts/container.py"]
