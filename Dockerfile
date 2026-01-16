FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONUNBUFFERED=1

# Exponha a porta apenas por documentação
EXPOSE 8080

# Use gunicorn e expanda $PORT via sh -c
CMD ["sh", "-c", "gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:${PORT:-8080} app:app"]
