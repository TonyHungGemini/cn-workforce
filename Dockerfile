FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CN_HOST=0.0.0.0 \
    CN_DATA_DIR=/data \
    CN_SEED_DEMO=0 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py auth.py drive.py store.py ./
COPY static ./static
COPY scripts ./scripts

RUN mkdir -p /data

EXPOSE 8080
CMD ["python", "app.py"]
