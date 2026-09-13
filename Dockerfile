FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
COPY mark1/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY mark1 /app
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 90 app:app"]
