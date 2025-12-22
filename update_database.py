import os
import psycopg2

def atualizar_estrutura_banco():
    """Atualizar estrutura do banco para incluir todos os campos"""
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        print("🔄 Conectando ao Railway PostgreSQL...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # DELETAR tabela pedidos existente para recriar completa
        print("🗑️ Removendo tabela pedidos antiga...")
        cursor.execute("DROP TABLE IF EXISTS pedidos CASCADE")
        
        # CRIAR tabela pedidos COMPLETA
        print("📋 Criando tabela pedidos completa...")
        cursor.execute("""
            CREATE TABLE pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                
                -- DADOS DO CABEÇALHO
                nome_representante VARCHAR(150) NOT NULL,
                razao_social VARCHAR(200) NOT NULL,
                cnpj_cliente VARCHAR(18) NOT NULL,
                telefone VARCHAR(20),
                
                -- CONDIÇÕES DO PEDIDO
                prazo_pagamento VARCHAR(100),
                tipo_pedido VARCHAR(10), -- OP ou PE
                numero_op VARCHAR(50), -- Novo campo
                tipo_frete VARCHAR(10), -- CIF ou FOB
                transportadora_fob TEXT,
                transportadora_cif TEXT,
                tipo_produto VARCHAR(50), -- Liso, Estampado, Digital
                venda_triangular VARCHAR(10), -- Sim/Não
                dados_triangulacao TEXT,
                regime_ret VARCHAR(10), -- Sim/Não
                
                -- TABELA DE PREÇOS
                tabela_precos VARCHAR(50), -- ICMS 18%, ICMS 12%, etc.
                
                -- OBSERVAÇÕES
                observacoes TEXT,
                
                -- VALOR TOTAL
                valor_total DECIMAL(12,2) DEFAULT 0,
                
                -- TIMESTAMPS
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # CRIAR tabela pedidos_itens COMPLETA
        print("📋 Criando tabela pedidos_itens...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos_itens (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) NOT NULL,
                
                -- DADOS DO PRODUTO
                artigo VARCHAR(100) NOT NULL,
                codigo VARCHAR(50) NOT NULL,
                desenho_cor VARCHAR(100) NOT NULL,
                metragem DECIMAL(10,2) NOT NULL,
                preco_metro DECIMAL(10,2) NOT NULL,
                subtotal DECIMAL(12,2) NOT NULL,
                
                -- FOREIGN KEY
                FOREIGN KEY (numero_pedido) REFERENCES pedidos(numero_pedido) ON DELETE CASCADE,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # CRIAR índices para performance
        print("📋 Criando índices...")
        cursor.execute("CREATE INDEX idx_pedidos_numero ON pedidos(numero_pedido)")
        cursor.execute("CREATE INDEX idx_pedidos_cnpj ON pedidos(cnpj_cliente)")
        cursor.execute("CREATE INDEX idx_pedidos_representante ON pedidos(nome_representante)")
        cursor.execute("CREATE INDEX idx_pedidos_data ON pedidos(created_at)")
        cursor.execute("CREATE INDEX idx_itens_pedido ON pedidos_itens(numero_pedido)")
        
        conn.commit()
        print("✅ Estrutura do banco atualizada com sucesso!")
        
        # Verificar tabelas criadas
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('pedidos', 'pedidos_itens')
            ORDER BY table_name, ordinal_position
        """)
        
        colunas = cursor.fetchall()
        
        print("\n📋 COLUNAS CRIADAS:")
        tabela_atual = ""
        for coluna in colunas:
            if coluna[0] != tabela_atual:
                tabela_atual = coluna[0]
                print(f"\n🔹 Tabela: {tabela_atual}")
            print(f"   ✅ {coluna[1]} ({coluna[2]})")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar banco: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == '__main__':
    atualizar_estrutura_banco()
