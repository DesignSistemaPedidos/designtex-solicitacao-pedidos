FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONUNBUFFERED=1

# Exponha a porta apenas por documentação
EXPOSE 8080

# Use gunicorn e expanda $PORT via sh -c
