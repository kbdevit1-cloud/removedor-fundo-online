FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV REMBG_MODEL=u2net
ENV CORS_ORIGINS=*
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
