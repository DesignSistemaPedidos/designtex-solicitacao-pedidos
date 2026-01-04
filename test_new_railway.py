import psycopg2

def testar_nova_database():
    """Testar nova DATABASE_URL do Railway"""
    
    print("🌐 TESTANDO NOVA DATABASE_URL DO RAILWAY")
    print("-" * 50)
    
    # Nova URL
    database_url = "postgresql://postgres:vnOYDTzqXEllZGIszbjXRciUvVOsBkHR@switchyard.proxy.rlwy.net:25577/railway"
    
    try:
        print("🔄 Conectando...")
        conn = psycopg2.connect(database_url)
        
        cursor = conn.cursor()
        
        # Testar conexão
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print(f"✅ Conectado! Version: {version[:60]}...")
        
        # Verificar tabelas
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tabelas = cursor.fetchall()
        
        print(f"📋 Tabelas encontradas: {len(tabelas)}")
        if tabelas:
            for tabela in tabelas:
                print(f"   ✅ {tabela[0]}")
        else:
            print("   📝 Banco vazio - pronto para inicializar")
        
        # Teste simples
        cursor.execute("SELECT 'Nova conexao Railway OK!' as teste")
        resultado = cursor.fetchone()
        print(f"🎯 Teste: {resultado[0]}")
        
        cursor.close()
        conn.close()
        
        print("🎉 NOVA DATABASE_URL FUNCIONANDO!")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == '__main__':
    testar_nova_database()
