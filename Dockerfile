# --- 1. Build the React frontend ---------------------------------------------
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Fetch the free DB-IP Lite geolocation databases (CC BY 4.0) ------------
# This month's release, falling back to last month's. If both fail the image still
# builds; the honeypot just records attempts without locations.
FROM python:3.12-slim AS geo
WORKDIR /geo
RUN python - <<'PY'
import datetime, gzip, os, shutil, urllib.request
today = datetime.date.today().replace(day=1)
months = [today, (today - datetime.timedelta(days=1)).replace(day=1)]
for kind, name in (("city", "city.mmdb"), ("asn", "asn.mmdb")):
    for m in months:
        url = f"https://download.db-ip.com/free/dbip-{kind}-lite-{m:%Y-%m}.mmdb.gz"
        try:
            # Some download hosts refuse Python's default user agent, so name ourselves.
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (whos-knocking build)"})
            with urllib.request.urlopen(req, timeout=120) as r, open(name + ".part", "wb") as out:
                shutil.copyfileobj(gzip.GzipFile(fileobj=r), out)
            os.replace(name + ".part", name)  # never leave a half-written database behind
            print("downloaded", url, os.path.getsize(name), "bytes")
            break
        except Exception as exc:
            print("could not fetch", url, exc)
            if os.path.exists(name + ".part"):
                os.remove(name + ".part")
PY

# --- 3. Tests (build with --target test; deploys refuse to continue if this fails) ---
FROM python:3.12-slim AS test
WORKDIR /src
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY backend/ ./
RUN ruff check . && ruff format --check . && pytest -q -p no:cacheprovider

# --- 4. Runtime ---------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    DATABASE_PATH=/app/data/attacks.db \
    STATIC_DIR=/app/static \
    GEO_CITY_DB=/app/geo/city.mmdb \
    GEO_ASN_DB=/app/geo/asn.mmdb \
    SENSOR_PORT=2222

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ app/
COPY --from=ui /ui/dist/ static/
COPY --from=geo /geo/ geo/

# Non-root; /app/data (a volume) is the only writable path. The honeypot listens on
# 2222 inside the container, so it never needs root to bind a low port.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 5000 2222

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).status == 200 else 1)"

# One worker on purpose: the live feed fans out from memory in this process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--no-server-header"]
