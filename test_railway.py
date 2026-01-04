import os
import psycopg2
import sys


def testar_railway():
    """Testar conexão com Railway PostgreSQL"""

    print("🌐 TESTANDO CONEXÃO RAILWAY POSTGRESQL")
    print("-" * 50)

    # URL do Railway
    database_url = "postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway"

    encodings = ['UTF8', 'LATIN1', 'SQL_ASCII']

    for encoding in encodings:
        try:
            print(f"🔄 Tentando conectar com encoding: {encoding}")

            # Adicionar encoding na URL
            url_com_encoding = f"{database_url}?client_encoding={encoding}"

            conn = psycopg2.connect(url_com_encoding)
            conn.set_client_encoding(encoding)

            cursor = conn.cursor()

            # Testar conexão
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
            print(f"✅ Conectado! Version: {version[:60]}...")

            # Verificar tabelas existentes
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tabelas = cursor.fetchall()

            print(f"📋 Tabelas encontradas no Railway: {len(tabelas)}")
            if tabelas:
                for tabela in tabelas:
                    print(f"   ✅ {tabela[0]}")
            else:
                print("   📝 Banco vazio - pronto para criar tabelas")

            # Testar operação básica
            cursor.execute("SELECT 'Conexao Railway OK' as teste")
            resultado = cursor.fetchone()
            print(f"🎯 Teste: {resultado[0]}")

            cursor.close()
            conn.close()

            print(f"🎉 RAILWAY POSTGRESQL FUNCIONANDO COM {encoding}!")
            return True

        except Exception as e:
            print(f"❌ Erro com encoding {encoding}: {str(e)[:100]}...")
            if 'conn' in locals() and conn:
                conn.close()
            continue

    print("❌ Não foi possível conectar ao Railway")
    return False


if __name__ == '__main__':
    testar_railway()
