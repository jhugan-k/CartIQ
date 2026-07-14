# Portable container image for the CartIQ API — deploy on Render, Fly, Railway,
# Cloud Run, or anywhere that runs Docker. (Render can also deploy natively via
# render.yaml — this Dockerfile is the portable alternative.)
FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The platform injects $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# Apply DB migrations, then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
