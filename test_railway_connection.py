import psycopg2
import time
from urllib.parse import urlparse


def testar_conexao_railway():
    """Testar conexão Railway com debugging detalhado"""

    database_url = "postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway"

    # Parse da URL
    parsed = urlparse(database_url)

    print("🔍 INFORMAÇÕES DA CONEXÃO RAILWAY:")
    print(f"   Host: {parsed.hostname}")
    print(f"   Port: {parsed.port}")
    print(f"   Database: {parsed.path[1:]}")
    print(f"   User: {parsed.username}")
    print(f"   Password: {'*' * len(parsed.password)}")
    print("-" * 50)

    # Várias tentativas com configurações diferentes
    configuracoes = [
        {
            'name': 'Configuração 1: Básica',
            'params': {'dsn': database_url, 'connect_timeout': 30}
        },
        {
            'name': 'Configuração 2: Com keepalive',
            'params': {
                'dsn': database_url,
                'connect_timeout': 30,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 3
            }
        },
        {
            'name': 'Configuração 3: SSL desabilitado',
            'params': {
                'dsn': f"{database_url}?sslmode=disable",
                'connect_timeout': 30
            }
        },
        {
            'name': 'Configuração 4: SSL preferido',
            'params': {
                'dsn': f"{database_url}?sslmode=prefer",
                'connect_timeout': 30
            }
        }
    ]

    for config in configuracoes:
        try:
            print(f"🔄 Testando: {config['name']}")

            start_time = time.time()
            conn = psycopg2.connect(**config['params'])
            connect_time = time.time() - start_time

            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]

            print(f"   ✅ SUCESSO! Tempo: {connect_time:.2f}s")
            print(f"   📋 {version[:60]}...")

            cursor.close()
            conn.close()

            print(f"🎉 CONFIGURAÇÃO QUE FUNCIONA: {config['name']}")
            return config

        except Exception as e:
            print(f"   ❌ Falhou: {str(e)[:100]}...")
            continue

    print("❌ Nenhuma configuração funcionou")
    return None


if __name__ == '__main__':
    testar_conexao_railway()
