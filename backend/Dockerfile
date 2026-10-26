FROM python:3.11-slim

WORKDIR /app

# Install OpenGL/OpenCASCADE runtime libraries and non-root execution user
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglu1-mesa \
    libxrender1 \
    libxcursor1 \
    libxft2 \
    libxinerama1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 pdeuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data/artifacts && chown -R pdeuser:pdeuser /app

USER pdeuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 30"]
