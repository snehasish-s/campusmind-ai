FROM node:22-bookworm-slim AS web-build
WORKDIR /build
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
ENV NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=http://127.0.0.1:8000
RUN npm run build

FROM python:3.13-slim-bookworm
COPY --from=web-build /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONPATH=/app/services/api NEXT_TELEMETRY_DISABLED=1 LANGSMITH_TRACING=false PYTHONUNBUFFERED=1
COPY services/api/requirements.lock.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/api/ services/api/
COPY infra/render_start.py infra/render_start.py
COPY --from=web-build /build/.next/standalone ./web
COPY --from=web-build /build/.next/static ./web/.next/static
RUN useradd --create-home campusmind && chown -R campusmind:campusmind /app
USER campusmind
EXPOSE 10000
CMD ["python", "infra/render_start.py"]
