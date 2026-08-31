# Pinned rather than :3-slim so a rebuild can't silently move Python versions.
# 3.14 matches the interpreter the code and test suite actually run on locally.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first: this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed ./seed
COPY schema.sql .

# Run unprivileged. The container writes nothing outside /tmp.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# $PORT is provided by the platform; default keeps `docker run` usable locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
