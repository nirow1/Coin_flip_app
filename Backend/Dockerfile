# Build context = Backend/ (set Railway Root Directory to Backend)
# Copy into /app/Backend so existing `from Backend...` imports keep working.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app/Backend/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["sh", "-c", "cd /app/Backend && alembic upgrade head && uvicorn Backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
