import psycopg2
import os

def debug_railway_completo():
    """Diagnóstico completo do Railway PostgreSQL"""
    
    print("🔍 DIAGNÓSTICO RAILWAY POSTGRESQL")
    print("=" * 60)
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        # Conectar
        print("🔄 Conectando ao Railway...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # 1. Verificar versão
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL Version: {version[:60]}...")
        
        # 2. Listar TODOS os schemas
        print(f"\n📂 SCHEMAS DISPONÍVEIS:")
        cursor.execute("""
            SELECT schema_name FROM information_schema.schemata 
            ORDER BY schema_name
        """)
        schemas = cursor.fetchall()
        for schema in schemas:
            print(f"   📁 {schema[0]}")
        
        # 3. Listar TODAS as tabelas (todos os schemas)
        print(f"\n📋 TODAS AS TABELAS:")
        cursor.execute("""
            SELECT table_schema, table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """)
        todas_tabelas = cursor.fetchall()
        
        if todas_tabelas:
            for tabela in todas_tabelas:
                print(f"   📄 {tabela[0]}.{tabela[1]} ({tabela[2]})")
        else:
            print("   ❌ NENHUMA TABELA ENCONTRADA!")
        
        # 4. Verificar especificamente schema 'public'
        print(f"\n🎯 TABELAS NO SCHEMA 'public':")
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas_public = cursor.fetchall()
        
        if tabelas_public:
            for tabela in tabelas_public:
                print(f"   ✅ {tabela[0]}")
        else:
            print("   ❌ SCHEMA 'public' ESTÁ VAZIO!")
        
        # 5. Se tem tabelas, verificar dados
        if tabelas_public:
            print(f"\n📊 VERIFICANDO DADOS NAS TABELAS:")
            
            tabelas_para_verificar = ['clientes', 'pedidos', 'precos_normal', 'precos_ld', 'sequencia_pedidos']
            
            for tabela_nome in tabelas_para_verificar:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {tabela_nome}")
                    count = cursor.fetchone()[0]
                    print(f"   📈 {tabela_nome}: {count} registros")
                    
                    if count > 0:
                        cursor.execute(f"SELECT * FROM {tabela_nome} LIMIT 3")
                        samples = cursor.fetchall()
                        for i, sample in enumerate(samples, 1):
                            print(f"      {i}. {sample}")
                            
                except Exception as e:
                    print(f"   ❌ {tabela_nome}: Erro - {str(e)[:50]}...")
        
        # 6. Verificar permissões
        print(f"\n🔐 VERIFICANDO PERMISSÕES:")
        cursor.execute("""
            SELECT current_user, session_user, current_database()
        """)
        permissoes = cursor.fetchone()
        print(f"   👤 Usuario atual: {permissoes[0]}")
        print(f"   👤 Usuario sessao: {permissoes[1]}")
        print(f"   🗄️  Database atual: {permissoes[2]}")
        
        # 7. Testar criação de tabela temporária
        print(f"\n🧪 TESTANDO CRIAÇÃO DE TABELA:")
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teste_temp (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("INSERT INTO teste_temp (nome) VALUES ('TESTE_CONEXAO')")
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM teste_temp")
            count = cursor.fetchone()[0]
            print(f"   ✅ Tabela teste criada com {count} registro(s)")
            
            # Limpar teste
            cursor.execute("DROP TABLE teste_temp")
            conn.commit()
            print(f"   🧹 Tabela teste removida")
            
        except Exception as e:
            print(f"   ❌ Erro ao criar tabela teste: {e}")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 DIAGNÓSTICO CONCLUÍDO!")
        
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")

if __name__ == '__main__':
    debug_railway_completo()
