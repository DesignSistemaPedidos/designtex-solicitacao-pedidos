import psycopg2

def verificar_dados_railway():
    """Verificar se os dados foram criados no Railway"""
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        print("🌐 VERIFICANDO DADOS NO RAILWAY")
        print("-" * 50)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar tabelas
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas = cursor.fetchall()
        
        print(f"📋 TABELAS CRIADAS NO RAILWAY: {len(tabelas)}")
        for tabela in tabelas:
            print(f"   ✅ {tabela[0]}")
        
        # Verificar clientes
        cursor.execute("SELECT COUNT(*) FROM clientes")
        count_clientes = cursor.fetchone()[0]
        print(f"\n👥 CLIENTES NO RAILWAY: {count_clientes}")
        
        cursor.execute("SELECT cnpj, razao_social FROM clientes")
        clientes = cursor.fetchall()
        for cliente in clientes:
            print(f"   📄 {cliente[0]} - {cliente[1]}")
        
        # Verificar preços
        cursor.execute("SELECT COUNT(*) FROM precos_normal")
        count_precos = cursor.fetchone()[0]
        print(f"\n💰 PREÇOS NO RAILWAY: {count_precos}")
        
        cursor.execute("SELECT artigo, icms_18 FROM precos_normal")
        precos = cursor.fetchall()
        for preco in precos:
            print(f"   💰 {preco[0]} - R$ {preco[1]}")
        
        # Verificar sequência
        cursor.execute("SELECT ultimo_numero FROM sequencia_pedidos WHERE id = 1")
        sequencia = cursor.fetchone()
        if sequencia:
            print(f"\n🔢 PRÓXIMO PEDIDO: {sequencia[0] + 1:04d}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 DADOS CONFIRMADOS NO RAILWAY POSTGRESQL!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == '__main__':
    verificar_dados_railway()
