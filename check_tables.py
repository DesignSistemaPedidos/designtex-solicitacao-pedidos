import psycopg2
import os

def verificar_estrutura_tabelas():
    """Verificar estrutura das tabelas"""
    
    # Configuração baseada no .env
    environment = os.getenv('ENVIRONMENT', 'development')
    
    if environment == 'production':
        print("🌐 Verificando tabelas no RAILWAY")
        database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
        conn = psycopg2.connect(database_url)
    else:
        print("🏠 Verificando tabelas no LOCAL")
        conn = psycopg2.connect(
            host='localhost',
            database='designtex_db',
            user='postgres',
            password='sua_senha_local',
            port='5432'
        )
    
    try:
        cursor = conn.cursor()
        
        # Verificar estrutura da tabela pedidos
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        colunas = cursor.fetchall()
        
        print("\n📋 ESTRUTURA ATUAL DA TABELA PEDIDOS:")
        print("-" * 60)
        for coluna in colunas:
            nome, tipo, nulo, default = coluna
            print(f"   📄 {nome} | {tipo} | NULL: {nulo} | Default: {default}")
        
        print(f"\n✅ Total de colunas: {len(colunas)}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == '__main__':
    verificar_estrutura_tabelas()
