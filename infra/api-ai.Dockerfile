FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace/services/api HF_HOME=/workspace/data/models
WORKDIR /workspace
COPY services/api/requirements.lock.txt /tmp/requirements.txt
COPY services/api/requirements-embeddings.txt services/api/requirements-ai.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && pip install --no-cache-dir -r /tmp/requirements-embeddings.txt && useradd --create-home --uid 10001 campusmind
COPY services /workspace/services
COPY scripts /workspace/scripts
RUN mkdir -p /workspace/data/storage /workspace/data/models && chown -R campusmind:campusmind /workspace
USER campusmind
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
