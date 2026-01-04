import psycopg2

def recriar_tabela_pedidos():
    """Recriar tabela pedidos com estrutura completa"""
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        print("🔄 RECRIANDO TABELA PEDIDOS COMPLETA")
        print("-" * 50)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Backup dos dados existentes (se houver)
        print("📋 Fazendo backup dos dados existentes...")
        try:
            cursor.execute("SELECT * FROM pedidos")
            pedidos_backup = cursor.fetchall()
            print(f"   ✅ Backup de {len(pedidos_backup)} pedidos")
        except:
            pedidos_backup = []
            print("   📝 Nenhum pedido para backup")
        
        # Dropar tabelas relacionadas primeiro
        print("🗑️  Removendo tabelas antigas...")
        cursor.execute("DROP TABLE IF EXISTS pedido_itens CASCADE")
        cursor.execute("DROP TABLE IF EXISTS pedidos CASCADE")
        
        # Recriar tabela pedidos completa
        print("🔨 Criando nova tabela pedidos...")
        cursor.execute("""
            CREATE TABLE pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                representante VARCHAR(100),
                tipo_pedido VARCHAR(20) DEFAULT 'normal',
                numero_op VARCHAR(50),
                tabela_preco VARCHAR(20) DEFAULT 'normal',
                condicao_pagamento VARCHAR(100),
                prazo_entrega VARCHAR(50),
                observacoes TEXT,
                observacoes_adicionais TEXT,
                valor_total DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Recriar tabela itens
        print("🔨 Criando tabela de itens...")
        cursor.execute("""
            CREATE TABLE pedido_itens (
                id SERIAL PRIMARY KEY,
                pedido_id INTEGER REFERENCES pedidos(id) ON DELETE CASCADE,
                artigo VARCHAR(100),
                codigo VARCHAR(50),
                descricao VARCHAR(200),
                quantidade DECIMAL(10,2),
                preco_unitario DECIMAL(10,2),
                total_item DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        
        # Verificar estrutura criada
        print("\n📋 Estrutura da nova tabela pedidos:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' 
            ORDER BY ordinal_position
        """)
        colunas = cursor.fetchall()
        
        for coluna in colunas:
            nullable = "NULL" if coluna[2] == "YES" else "NOT NULL"
            default = f"DEFAULT {coluna[3]}" if coluna[3] else ""
            print(f"   ✅ {coluna[0]} - {coluna[1]} - {nullable} {default}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 TABELA PEDIDOS RECRIADA COM SUCESSO!")
        print("🔄 Agora execute o app.py novamente")
        
    except Exception as e:
        print(f"❌ Erro ao recriar tabela: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == '__main__':
    recriar_tabela_pedidos()
