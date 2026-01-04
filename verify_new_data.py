import psycopg2

def verificar_novo_banco():
    """Verificar dados no novo banco Railway"""
    
    database_url = "postgresql://postgres:vnOYDTzqXEllZGIszbjXRciUvVOsBkHR@switchyard.proxy.rlwy.net:25577/railway"
    
    try:
        print("🌐 VERIFICANDO DADOS NO NOVO RAILWAY")
        print("-" * 50)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Tabelas
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas = cursor.fetchall()
        
        print(f"📋 TABELAS NO NOVO RAILWAY: {len(tabelas)}")
        for tabela in tabelas:
            print(f"   ✅ {tabela[0]}")
        
        # Clientes
        cursor.execute("SELECT COUNT(*) FROM clientes")
        count_clientes = cursor.fetchone()[0]
        print(f"\n👥 CLIENTES: {count_clientes}")
        
        if count_clientes > 0:
            cursor.execute("SELECT cnpj, razao_social FROM clientes LIMIT 3")
            clientes = cursor.fetchall()
            for cliente in clientes:
                print(f"   📄 {cliente[0]} - {cliente[1]}")
        
        # Preços
        cursor.execute("SELECT COUNT(*) FROM precos_normal")
        count_precos = cursor.fetchone()[0]
        print(f"\n💰 PREÇOS: {count_precos}")
        
        if count_precos > 0:
            cursor.execute("SELECT artigo, icms_18 FROM precos_normal LIMIT 3")
            precos = cursor.fetchall()
            for preco in precos:
                print(f"   💰 {preco[0]} - R$ {preco[1]}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 NOVO BANCO RAILWAY CONFIGURADO!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == '__main__':
    verificar_novo_banco()
