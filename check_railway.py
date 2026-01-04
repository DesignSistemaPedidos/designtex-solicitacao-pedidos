import psycopg2
import sys
import os

# CONFIGURAR ENCODING ANTES DE TUDO
os.environ['PYTHONIOENCODING'] = 'utf-8'

def verificar_railway():
    """Verificar dados no Railway PostgreSQL"""
    
    print("🌐 VERIFICANDO RAILWAY POSTGRESQL")
    print("-" * 50)
    
    # URL do Railway
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    try:
        # Conectar com encoding seguro
        conn = psycopg2.connect(f"{database_url}?client_encoding=UTF8")
        conn.set_client_encoding('UTF8')
        
        cursor = conn.cursor()
        
        # Verificar versão
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL: {version[:60]}...")
        
        # Verificar tabelas
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas = cursor.fetchall()
        
        print(f"\n📋 TABELAS NO RAILWAY: {len(tabelas)}")
        for tabela in tabelas:
            print(f"   ✅ {tabela[0]}")
        
        if len(tabelas) > 0:
            # Verificar clientes
            try:
                cursor.execute("SELECT COUNT(*) FROM clientes")
                count_clientes = cursor.fetchone()[0]
                print(f"\n👥 CLIENTES: {count_clientes}")
                
                cursor.execute("SELECT cnpj, razao_social FROM clientes LIMIT 3")
                clientes = cursor.fetchall()
                for cliente in clientes:
                    print(f"   📄 {cliente[0]} - {cliente[1]}")
            except:
                print("\n👥 CLIENTES: Tabela vazia ou não existe")
            
            # Verificar preços
            try:
                cursor.execute("SELECT COUNT(*) FROM precos_normal")
                count_precos = cursor.fetchone()[0]
                print(f"\n💰 PREÇOS: {count_precos}")
                
                cursor.execute("SELECT artigo, icms_18 FROM precos_normal LIMIT 3")
                precos = cursor.fetchall()
                for preco in precos:
                    print(f"   💰 {preco[0]} - R$ {preco[1]}")
            except:
                print("\n💰 PREÇOS: Tabela vazia ou não existe")
        else:
            print("\n📝 Banco vazio - execute 'python app.py' para criar tabelas")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 RAILWAY POSTGRESQL VERIFICADO COM SUCESSO!")
        
    except Exception as e:
        print(f"❌ Erro ao verificar Railway: {e}")

if __name__ == '__main__':
    verificar_railway()
