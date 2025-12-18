import os
import psycopg2
from datetime import datetime

def testar_railway_postgresql():
    """Testar conexão com Railway PostgreSQL"""
    
    print("🌐 TESTANDO RAILWAY POSTGRESQL")
    print("=" * 50)
    print(f"🕐 Horário: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    # Sua DATABASE_URL do Railway
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    encodings = ['UTF8', 'LATIN1', 'SQL_ASCII']
    
    for encoding in encodings:
        try:
            print(f"🔄 Tentando conectar com encoding: {encoding}")
            
            # Adicionar encoding na URL
            url_with_encoding = f"{database_url}?client_encoding={encoding}"
            
            # Conectar
            conn = psycopg2.connect(url_with_encoding)
            conn.set_client_encoding(encoding)
            
            cursor = conn.cursor()
            
            # Testar versão
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
            print(f"✅ CONECTADO! PostgreSQL: {version[:60]}...")
            
            # Testar tabelas existentes
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            tabelas = cursor.fetchall()
            
            print(f"📋 Tabelas encontradas: {len(tabelas)}")
            if tabelas:
                for tabela in tabelas:
                    print(f"   • {tabela[0]}")
            else:
                print("   (Nenhuma tabela encontrada - banco vazio)")
            
            # Testar criação de tabela simples
            print("\n🧪 Testando criação de tabela...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teste_conexao (
                    id SERIAL PRIMARY KEY,
                    teste VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                INSERT INTO teste_conexao (teste) 
                VALUES ('Conexao Railway OK') 
                ON CONFLICT DO NOTHING
            """)
            
            cursor.execute("SELECT COUNT(*) FROM teste_conexao")
            count = cursor.fetchone()[0]
            print(f"✅ Tabela teste_conexao: {count} registros")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"\n🎉 RAILWAY POSTGRESQL FUNCIONANDO COM {encoding}!")
            print("🌐 Pronto para usar na nuvem!")
            break
            
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                print(f"❌ Timeout na conexão: {error_msg[:100]}...")
            elif "authentication" in error_msg.lower():
                print(f"❌ Erro de autenticação: {error_msg[:100]}...")
            elif "host" in error_msg.lower():
                print(f"❌ Erro de host/porta: {error_msg[:100]}...")
            else:
                print(f"❌ Erro de conexão: {error_msg[:100]}...")
            
            if encoding == encodings[-1]:  # Último encoding
                print("\n❌ NÃO FOI POSSÍVEL CONECTAR AO RAILWAY")
                print("🔧 Possíveis soluções:")
                print("   1. Verificar se o serviço Railway está ativo")
                print("   2. Verificar se a porta está liberada")
                print("   3. Tentar novamente em alguns minutos")
            continue
            
        except UnicodeDecodeError as e:
            print(f"❌ Erro de encoding {encoding}: {str(e)[:100]}...")
            continue
            
        except Exception as e:
            print(f"❌ Erro geral: {str(e)[:100]}...")
            continue

if __name__ == '__main__':
    testar_railway_postgresql()
