import psycopg2
import os


def verificar_e_corrigir_tabelas():
    """Verificar e corrigir estrutura das tabelas"""

    # URL do Railway
    database_url = "postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway"

    try:
        print("🔍 VERIFICANDO ESTRUTURA DAS TABELAS")
        print("-" * 50)

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Verificar colunas da tabela pedidos
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' 
            ORDER BY ordinal_position
        """)
        colunas_pedidos = cursor.fetchall()

        print("📋 COLUNAS DA TABELA PEDIDOS:")
        for coluna in colunas_pedidos:
            print(f"   - {coluna[0]} ({coluna[1]}) - Nullable: {coluna[2]}")

        # Verificar se coluna status existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' AND column_name = 'status'
        """)
        tem_status = cursor.fetchone()[0] > 0

        if not tem_status:
            print("\n❌ COLUNA 'status' NÃO EXISTE - VAMOS ADICIONAR")

            # Adicionar coluna status
            cursor.execute("""
                ALTER TABLE pedidos 
                ADD COLUMN status VARCHAR(20) DEFAULT 'ATIVO'
            """)

            # Atualizar registros existentes
            cursor.execute("""
                UPDATE pedidos 
                SET status = 'ATIVO' 
                WHERE status IS NULL
            """)

            print("✅ COLUNA 'status' ADICIONADA COM SUCESSO")

        else:
            print("\n✅ COLUNA 'status' JÁ EXISTE")

        # Verificar se precisamos adicionar outras colunas
        colunas_necessarias = [
            ('items', 'TEXT'),
            ('data_entrega', 'DATE'),
            ('desconto', 'DECIMAL(5,2)'),
            ('frete', 'DECIMAL(10,2)')
        ]

        for nome_coluna, tipo_coluna in colunas_necessarias:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'pedidos' AND column_name = %s
            """, (nome_coluna,))

            existe = cursor.fetchone()[0] > 0

            if not existe:
                print(f"➕ Adicionando coluna: {nome_coluna}")
                cursor.execute(f"""
                    ALTER TABLE pedidos 
                    ADD COLUMN {nome_coluna} {tipo_coluna}
                """)
            else:
                print(f"✅ Coluna {nome_coluna} já existe")

        # Criar tabela de itens do pedido se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedido_items (
                id SERIAL PRIMARY KEY,
                pedido_id INTEGER REFERENCES pedidos(id) ON DELETE CASCADE,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                quantidade DECIMAL(10,2),
                preco_unitario DECIMAL(10,2),
                total_item DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabela pedido_items verificada/criada")

        # Confirmar mudanças
        conn.commit()

        # Verificar estrutura final
        print("\n📋 ESTRUTURA FINAL DA TABELA PEDIDOS:")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' 
            ORDER BY ordinal_position
        """)
        colunas_finais = cursor.fetchall()

        for coluna in colunas_finais:
            print(f"   ✅ {coluna[0]} ({coluna[1]})")

        cursor.close()
        conn.close()

        print("\n🎉 ESTRUTURA DO BANCO CORRIGIDA!")

    except Exception as e:
        print(f"❌ Erro: {e}")
        if conn:
            conn.rollback()
            conn.close()


if __name__ == '__main__':
    verificar_e_corrigir_tabelas()
