FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "-t", "60", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
