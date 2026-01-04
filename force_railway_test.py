from app import get_database_config, conectar_postgresql
import psycopg2
import os

# FORÇAR RAILWAY
os.environ['ENVIRONMENT'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway'

# Importar depois de definir as variáveis


def teste_forcado():
    print("🔧 TESTE FORÇADO RAILWAY")
    print("-" * 30)

    # Verificar configuração
    config = get_database_config()
    print(f"Configuração: {config}")

    # Testar conexão
    conn = conectar_postgresql()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Conectado: {version[:50]}...")

        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        tabelas = cursor.fetchone()[0]
        print(f"📋 Tabelas no Railway: {tabelas}")

        cursor.close()
        conn.close()
    else:
        print("❌ Falha na conexão")


if __name__ == '__main__':
    teste_forcado()
