import psycopg2
import time
from contextlib import closing

def testar_railway_robusto():
    """Testar Railway com timeout e retry"""
    
    database_url = "postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway"
    
    print("🌐 TESTE ROBUSTO RAILWAY POSTGRESQL")
    print("-" * 50)
    
    max_tentativas = 5
    timeout_inicial = 30
    
    for tentativa in range(1, max_tentativas + 1):
        try:
            print(f"🔄 Tentativa {tentativa}/{max_tentativas}")
            print(f"⏰ Timeout: {timeout_inicial}s")
            
            # URL com timeout maior
            url_timeout = f"{database_url}?connect_timeout={timeout_inicial}&client_encoding=UTF8"
            
            print("📡 Conectando...")
            with closing(psycopg2.connect(url_timeout)) as conn:
                with closing(conn.cursor()) as cursor:
                    
                    # Testar conexão
                    print("🔍 Testando conexão...")
                    cursor.execute('SELECT version();')
                    version = cursor.fetchone()[0]
                    
                    print(f"✅ SUCESSO! Version: {version[:50]}...")
                    
                    # Verificar tabelas
                    cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    count_tabelas = cursor.fetchone()[0]
                    print(f"📋 Tabelas: {count_tabelas}")
                    
                    print("🎉 RAILWAY POSTGRESQL FUNCIONANDO!")
                    return True
                    
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            
            if "server closed the connection" in error_msg:
                print(f"😴 Service dormindo. Aguardando despertar...")
                tempo_espera = 30 + (tentativa * 10)  # Aumenta tempo de espera
                print(f"⏳ Aguardando {tempo_espera}s antes da próxima tentativa...")
                time.sleep(tempo_espera)
                
            elif "timeout" in error_msg:
                print(f"⏰ Timeout. Aumentando tempo limite...")
                timeout_inicial += 15
                time.sleep(10)
                
            else:
                print(f"❌ Erro de conexão: {error_msg}")
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Erro geral: {str(e)}")
            time.sleep(5)
    
    print("❌ Não foi possível conectar após todas as tentativas")
    return False

if __name__ == '__main__':
    testar_railway_robusto()
