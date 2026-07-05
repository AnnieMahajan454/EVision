FROM python:3.11-slim

WORKDIR /app

# Install runtime deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application
COPY backend /app
COPY ml /app/ml

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

COPY backend/start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
