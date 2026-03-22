FROM python:3.11-slim

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir ".[nlm]" && \
    playwright install chromium --with-deps || true

EXPOSE 8000

CMD ["python", "-m", "notebooklm_toolkit"]
