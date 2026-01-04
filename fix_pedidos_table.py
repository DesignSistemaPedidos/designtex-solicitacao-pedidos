import psycopg2
import os

def corrigir_tabela_pedidos():
    """Corrigir estrutura da tabela pedidos"""
    
    # URL do Railway
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        print("🔧 CORRIGINDO ESTRUTURA DA TABELA PEDIDOS")
        print("-" * 50)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar estrutura atual
        print("📋 Verificando colunas atuais...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        colunas_atuais = cursor.fetchall()
        
        print("📝 Colunas existentes:")
        for coluna in colunas_atuais:
            print(f"   - {coluna[0]} ({coluna[1]})")
        
        # Adicionar colunas que faltam
        colunas_para_adicionar = [
            ('tipo_pedido', 'VARCHAR(50)'),
            ('numero_op', 'VARCHAR(20)'),
            ('tabela_preco', 'VARCHAR(20)'),
            ('icms', 'VARCHAR(10)'),
            ('prazo_entrega', 'VARCHAR(100)'),
            ('condicoes_pagamento', 'VARCHAR(200)'),
            ('itens_json', 'TEXT')
        ]
        
        print("\n🔄 Adicionando colunas faltantes...")
        
        for coluna_nome, coluna_tipo in colunas_para_adicionar:
            try:
                # Verificar se coluna já existe
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'pedidos' AND column_name = %s
                """, (coluna_nome,))
                
                if cursor.fetchone():
                    print(f"   ✅ {coluna_nome} já existe")
                else:
                    # Adicionar coluna
                    cursor.execute(f"""
                        ALTER TABLE pedidos 
                        ADD COLUMN {coluna_nome} {coluna_tipo}
                    """)
                    print(f"   ➕ Adicionada: {coluna_nome} ({coluna_tipo})")
                    
            except Exception as e:
                print(f"   ⚠️  Erro ao adicionar {coluna_nome}: {e}")
        
        # Verificar estrutura final
        print("\n📋 Estrutura final da tabela pedidos:")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        colunas_finais = cursor.fetchall()
        
        for coluna in colunas_finais:
            tipo = coluna[1]
            if coluna[2]:  # Se tem tamanho máximo
                tipo += f"({coluna[2]})"
            print(f"   ✅ {coluna[0]} - {tipo}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 TABELA PEDIDOS CORRIGIDA COM SUCESSO!")
        
    except Exception as e:
        print(f"❌ Erro ao corrigir tabela: {e}")

if __name__ == '__main__':
    corrigir_tabela_pedidos()
