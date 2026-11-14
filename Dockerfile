FROM python:3.12-slim

# The git commit this image was built from; shown by /healthz and /api/status.
ARG BSS_VERSION=dev

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BSS_DATA_DIR=/app/data BSS_VERSION=${BSS_VERSION}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

# Run as an unprivileged user. The data folder mounted at /app/data must be writable by uid 10001
# (deploy/server-setup.sh does this on the server; Docker Desktop on Windows/Mac needs nothing).
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin studio \
    && mkdir -p /app/data && chown studio:studio /app/data
USER studio

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

# One worker on purpose: PDF reading runs in a background thread, login throttling is in memory,
# and SQLite allows one writer. --proxy-headers: the app sits behind Caddy, which sets X-Forwarded-*.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
