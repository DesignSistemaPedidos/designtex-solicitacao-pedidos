import os
from app import app, init_database

# Opcional: inicializar DB na subida do app (seguro por ser idempotente)
if os.getenv('INIT_DB_ON_BOOT', '1') == '1':
    try:
        init_database()
    except Exception as e:
        print(f"⚠️  Falha ao inicializar DB no boot (segue assim mesmo): {e}")

# Expor o objeto 'app' para o Gunicorn
# Gunicorn irá usar: wsgi:app
