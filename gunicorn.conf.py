# gunicorn.conf.py
import os
import multiprocessing

# Bind dinâmico para a porta do Railway
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Workers e threads com valores padrão ajustáveis por env
workers = int(os.getenv("GUNICORN_WORKERS", (multiprocessing.cpu_count() * 2) + 1))
threads = int(os.getenv("GUNICORN_THREADS", 2))

# Classe de worker estável para Flask
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

# Tempo máximo de resposta e keepalive
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 30))

# Logs no stdout/stderr (Railway capta)
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
