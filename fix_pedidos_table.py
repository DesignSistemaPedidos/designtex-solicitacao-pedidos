import psycopg2
import os

def verificar_e_corrigir_tabela_pedidos():
    """Verificar e corrigir estrutura da tabela pedidos"""
    
    # Usar Railway
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        print("🔍 VERIFICANDO ESTRUTURA DA TABELA PEDIDOS")
        print("-" * 50)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar colunas existentes
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' 
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        colunas_existentes = cursor.fetchall()
        
        print("📋 COLUNAS EXISTENTES NA TABELA PEDIDOS:")
        for coluna in colunas_existentes:
            print(f"   ✅ {coluna[0]} ({coluna[1]})")
        
        # Verificar se falta alguma coluna
        colunas_necessarias = [
            'razao_social_cliente',
            'nome_fantasia_cliente', 
            'representante',
            'observacoes',
            'itens_json',
            'valor_total'
        ]
        
        colunas_faltando = []
        colunas_atuais = [col[0] for col in colunas_existentes]
        
        for coluna in colunas_necessarias:
            if coluna not in colunas_atuais:
                colunas_faltando.append(coluna)
        
        if colunas_faltando:
            print(f"\n❌ COLUNAS FALTANDO: {colunas_faltando}")
            print("🔧 ADICIONANDO COLUNAS...")
            
            # Adicionar colunas faltando
            alter_commands = []
            
            if 'razao_social_cliente' in colunas_faltando:
                alter_commands.append("ADD COLUMN razao_social_cliente VARCHAR(200)")
            if 'nome_fantasia_cliente' in colunas_faltando:
                alter_commands.append("ADD COLUMN nome_fantasia_cliente VARCHAR(150)")
            if 'representante' not in colunas_atuais:
                alter_commands.append("ADD COLUMN representante VARCHAR(100)")
            if 'observacoes' not in colunas_atuais:
                alter_commands.append("ADD COLUMN observacoes TEXT")
            if 'itens_json' in colunas_faltando:
                alter_commands.append("ADD COLUMN itens_json TEXT")
            if 'valor_total' not in colunas_atuais:
                alter_commands.append("ADD COLUMN valor_total DECIMAL(10,2)")
            
            # Executar ALTER TABLE
            for command in alter_commands:
                sql = f"ALTER TABLE pedidos {command}"
                print(f"   🔧 Executando: {sql}")
                cursor.execute(sql)
            
            conn.commit()
            print("✅ Colunas adicionadas com sucesso!")
            
        else:
            print("✅ Todas as colunas necessárias já existem!")
        
        # Verificar estrutura final
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' 
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        colunas_finais = cursor.fetchall()
        
        print("\n📋 ESTRUTURA FINAL DA TABELA PEDIDOS:")
        for coluna in colunas_finais:
            print(f"   ✅ {coluna[0]} ({coluna[1]})")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 TABELA PEDIDOS CORRIGIDA!")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == '__main__':
    verificar_e_corrigir_tabela_pedidos()
