FROM python:3.12-slim

WORKDIR /app

# Dependências
RUN pip install --no-cache-dir google-cloud-storage google-cloud-firestore

# Código do job
COPY lifecycle_job/ /app/lifecycle_job/
COPY pipeline/shared/ /app/shared/ 2>/dev/null || true

WORKDIR /app/lifecycle_job

CMD ["python", "-m", "lifecycle_job"]
