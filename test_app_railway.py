import os
import sys

# Simular o ambiente Railway
os.environ['ENVIRONMENT'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway'

# Importar funções do app
sys.path.append('.')


def test_app_railway_connection():
    """Testar se o app.py conecta corretamente ao Railway"""

    print("🧪 TESTANDO CONEXÃO APP.PY COM RAILWAY")
    print("=" * 50)

    try:
        # Simular as funções do app.py
        from app import conectar_postgresql, init_database

        print("✅ Funções importadas com sucesso")

        # Testar conexão
        print("\n🔄 Testando conectar_postgresql()...")
        conn = conectar_postgresql()

        if conn:
            print("✅ Conexão Railway estabelecida pelo app.py!")

            cursor = conn.cursor()
            cursor.execute("SELECT current_database()")
            db_name = cursor.fetchone()[0]
            print(f"📋 Database conectada: {db_name}")

            cursor.close()
            conn.close()

            # Testar inicialização
            print("\n🔄 Testando init_database()...")
            result = init_database()

            if result:
                print("✅ init_database() executou com sucesso!")
            else:
                print("❌ init_database() falhou!")

        else:
            print("❌ Falha na conexão Railway!")

    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_app_railway_connection()
