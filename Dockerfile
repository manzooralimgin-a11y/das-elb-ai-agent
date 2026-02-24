FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# Copy application code and migration script
COPY app/ ./app/
COPY migrate_db.py .

# Render sets PORT env var automatically (default 10000)
# Local default: 8080
EXPOSE 10000

# Use shell form so $PORT is expanded at runtime
# Run the DB migration script first, then start the server
CMD python migrate_db.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
