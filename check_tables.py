import psycopg2

def verificar_tabelas_railway():
    """Verificar exatamente que tabelas existem no Railway"""
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        print("🔍 DIAGNÓSTICO - TABELAS NO RAILWAY")
        print("=" * 50)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Listar TODAS as tabelas
        cursor.execute("""
            SELECT schemaname, tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        tabelas = cursor.fetchall()
        
        print(f"📋 TABELAS ENCONTRADAS: {len(tabelas)}")
        for schema, tabela in tabelas:
            print(f"   ✅ {schema}.{tabela}")
        
        # Se não tem tabelas, listar todos os schemas
        if not tabelas:
            print("\n🔍 VERIFICANDO OUTROS SCHEMAS...")
            cursor.execute("SELECT schema_name FROM information_schema.schemata")
            schemas = cursor.fetchall()
            for schema in schemas:
                print(f"   📂 Schema: {schema[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro no diagnóstico: {e}")

if __name__ == '__main__':
    verificar_tabelas_railway()
