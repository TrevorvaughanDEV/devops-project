FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATABASE_PATH=/app/data/metrics.db \
    WEB_CONCURRENCY=2

WORKDIR /app

# Dependencies first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/

# Run as a non-root user; /app/data is the only writable path (mounted as a volume)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 5000

# python:slim has no curl, so the health check uses Python's standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).status == 200 else 1)"

# Gunicorn reads the worker count from WEB_CONCURRENCY (2 suits a 1 GB VM)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "60", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
