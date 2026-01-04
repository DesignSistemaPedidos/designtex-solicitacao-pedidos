import psycopg2
import os

def atualizar_tabela_pedidos():
    """Atualizar estrutura da tabela pedidos com todos os campos necessários"""
    
    # Configuração baseada no .env
    environment = os.getenv('ENVIRONMENT', 'development')
    
    if environment == 'production':
        print("🌐 Atualizando tabela no RAILWAY")
        database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
        conn = psycopg2.connect(database_url)
    else:
        print("🏠 Atualizando tabela no LOCAL")
        conn = psycopg2.connect(
            host='localhost',
            database='designtex_db',
            user='postgres',
            password='sua_senha_local',
            port='5432'
        )
    
    try:
        cursor = conn.cursor()
        
        print("🔄 Adicionando colunas que estão faltando...")
        
        # Lista de colunas para adicionar (se não existirem)
        colunas_para_adicionar = [
            ("tipo_pedido", "VARCHAR(20) DEFAULT 'NORMAL'"),
            ("numero_op", "VARCHAR(20)"),
            ("tabela_preco", "VARCHAR(20) DEFAULT 'NORMAL'"),
            ("status_pedido", "VARCHAR(20) DEFAULT 'PENDENTE'"),
            ("data_entrega", "DATE"),
            ("desconto_percentual", "DECIMAL(5,2) DEFAULT 0"),
            ("frete", "DECIMAL(10,2) DEFAULT 0"),
            ("comissao", "DECIMAL(10,2) DEFAULT 0"),
            ("endereco_entrega", "TEXT"),
            ("cidade_entrega", "VARCHAR(100)"),
            ("uf_entrega", "VARCHAR(2)"),
            ("cep_entrega", "VARCHAR(10)"),
            ("transportadora", "VARCHAR(100)"),
            ("prazo_pagamento", "VARCHAR(50)"),
            ("forma_pagamento", "VARCHAR(50)"),
            ("vendedor", "VARCHAR(100)"),
            ("gerente", "VARCHAR(100)"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for coluna_nome, coluna_tipo in colunas_para_adicionar:
            try:
                # Verificar se a coluna já existe
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'pedidos' 
                    AND table_schema = 'public' 
                    AND column_name = %s
                """, (coluna_nome,))
                
                existe = cursor.fetchone()
                
                if not existe:
                    # Adicionar a coluna
                    sql = f"ALTER TABLE pedidos ADD COLUMN {coluna_nome} {coluna_tipo}"
                    cursor.execute(sql)
                    print(f"   ✅ Adicionada coluna: {coluna_nome}")
                else:
                    print(f"   📋 Coluna já existe: {coluna_nome}")
                    
            except Exception as e:
                print(f"   ❌ Erro na coluna {coluna_nome}: {e}")
        
        # Criar índices para melhor performance
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_cnpj ON pedidos(cnpj_cliente)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status_pedido)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_data ON pedidos(created_at)")
            print("   ✅ Índices criados")
        except Exception as e:
            print(f"   ⚠️  Aviso sobre índices: {e}")
        
        # Commit das mudanças
        conn.commit()
        print("🎉 Tabela pedidos atualizada com sucesso!")
        
        # Verificar estrutura final
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        colunas = cursor.fetchall()
        print(f"\n📋 ESTRUTURA FINAL DA TABELA PEDIDOS ({len(colunas)} colunas):")
        for coluna in colunas:
            print(f"   📄 {coluna[0]} ({coluna[1]})")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == '__main__':
    atualizar_tabela_pedidos()
