import psycopg2
import time
import os
from psycopg2.extras import RealDictCursor

class RailwayPostgreSQL:
    """Classe para conexão robusta com Railway PostgreSQL"""
    
    def __init__(self, database_url, max_retries=3):
        self.database_url = database_url
        self.max_retries = max_retries
        self.connection = None
    
    def connect_with_retry(self):
        """Conectar com retry automático"""
        
        for tentativa in range(1, self.max_retries + 1):
            try:
                print(f"🔄 Tentativa {tentativa}/{self.max_retries} - Conectando Railway...")
                
                # Configurações de conexão robustas
                self.connection = psycopg2.connect(
                    self.database_url,
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5
                )
                
                # Configurar autocommit para evitar transações longas
                self.connection.autocommit = True
                
                # Testar conexão
                cursor = self.connection.cursor()
                cursor.execute('SELECT 1')
                cursor.fetchone()
                cursor.close()
                
                print(f"✅ Conectado Railway na tentativa {tentativa}!")
                return True
                
            except Exception as e:
                print(f"❌ Tentativa {tentativa} falhou: {str(e)[:80]}...")
                
                if self.connection:
                    self.connection.close()
                    self.connection = None
                
                if tentativa < self.max_retries:
                    wait_time = tentativa * 2  # 2s, 4s, 6s
                    print(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
                    time.sleep(wait_time)
        
        print("❌ Falha em todas as tentativas de conexão")
        return False
    
    def execute_query(self, query, params=None, fetch=False):
        """Executar query com retry automático"""
        
        max_query_retries = 2
        
        for tentativa in range(max_query_retries):
            try:
                # Verificar se conexão está ativa
                if not self.connection or self.connection.closed:
                    print("🔄 Reconectando...")
                    if not self.connect_with_retry():
                        return None
                
                cursor = self.connection.cursor(cursor_factory=RealDictCursor)
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if fetch:
                    resultado = cursor.fetchall()
                    cursor.close()
                    return resultado
                else:
                    cursor.close()
                    return True
                    
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"❌ Erro de conexão na query (tentativa {tentativa + 1}): {str(e)[:60]}...")
                
                if self.connection:
                    self.connection.close()
                    self.connection = None
                
                if tentativa == 0:  # Tentar reconectar apenas uma vez
                    time.sleep(2)
                    continue
                else:
                    return None
                    
            except Exception as e:
                print(f"❌ Erro na query: {str(e)[:80]}...")
                return None
        
        return None
    
    def close(self):
        """Fechar conexão"""
        if self.connection and not self.connection.closed:
            self.connection.close()

# TESTAR A CLASSE
def testar_conexao_robusta():
    """Testar conexão robusta com Railway"""
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    print("🧪 TESTANDO CONEXÃO ROBUSTA RAILWAY")
    print("-" * 50)
    
    # Criar instância da classe
    db = RailwayPostgreSQL(database_url, max_retries=3)
    
    # Tentar conectar
    if db.connect_with_retry():
        
        # Teste 1: Query simples
        print("\n🧪 Teste 1: Query simples")
        resultado = db.execute_query("SELECT version()", fetch=True)
        if resultado:
            print(f"✅ Version: {resultado[0]['version'][:50]}...")
        
        # Teste 2: Listar tabelas
        print("\n🧪 Teste 2: Listar tabelas")
        resultado = db.execute_query("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """, fetch=True)
        
        if resultado:
            print(f"✅ Tabelas encontradas: {len(resultado)}")
            for tabela in resultado:
                print(f"   - {tabela['table_name']}")
        else:
            print("📝 Nenhuma tabela encontrada")
        
        # Teste 3: Criar tabela de teste
        print("\n🧪 Teste 3: Criar tabela de teste")
        sucesso = db.execute_query("""
            CREATE TABLE IF NOT EXISTS teste_conexao (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if sucesso:
            print("✅ Tabela de teste criada")
            
            # Inserir dados de teste
            sucesso = db.execute_query("""
                INSERT INTO teste_conexao (nome) VALUES (%s)
            """, ("Teste Railway Connection",))
            
            if sucesso:
                print("✅ Dados de teste inseridos")
                
                # Buscar dados
                resultado = db.execute_query("""
                    SELECT * FROM teste_conexao ORDER BY id DESC LIMIT 1
                """, fetch=True)
                
                if resultado:
                    print(f"✅ Dados recuperados: {resultado[0]['nome']}")
        
        print("\n🎉 CONEXÃO ROBUSTA FUNCIONANDO!")
        
    else:
        print("❌ Falha na conexão robusta")
    
    # Fechar conexão
    db.close()

if __name__ == '__main__':
    testar_conexao_robusta()
