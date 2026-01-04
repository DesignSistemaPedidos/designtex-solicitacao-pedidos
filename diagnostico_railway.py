import socket
import psycopg2
import os
import time
from urllib.parse import urlparse

def diagnostico_completo():
    """Diagnóstico completo da conexão Railway"""
    
    print("🔍 DIAGNÓSTICO RAILWAY POSTGRESQL")
    print("=" * 50)
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    
    # Parse da URL
    parsed = urlparse(database_url)
    host = parsed.hostname
    port = parsed.port
    username = parsed.username
    password = parsed.password
    database = parsed.path[1:]
    
    print(f"🌐 Host: {host}")
    print(f"🔌 Porta: {port}")
    print(f"👤 User: {username}")
    print(f"🗃️  Database: {database}")
    print(f"🔐 Password: {password[:3]}***{password[-3:]}")
    print("-" * 50)
    
    # TESTE 1: DNS Resolution
    print("🔍 TESTE 1: Resolução DNS")
    try:
        ip = socket.gethostbyname(host)
        print(f"✅ DNS OK: {host} → {ip}")
    except Exception as e:
        print(f"❌ DNS FALHOU: {e}")
        return False
    
    # TESTE 2: Conectividade TCP
    print("\n🔍 TESTE 2: Conectividade TCP")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10 segundos timeout
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ TCP OK: Porta {port} acessível")
        else:
            print(f"❌ TCP FALHOU: Porta {port} inacessível (código: {result})")
            print("🔧 POSSÍVEIS CAUSAS:")
            print("   • Firewall corporativo bloqueando a porta")
            print("   • Antivírus bloqueando conexão")
            print("   • ISP bloqueando portas não-padrão")
            print("   • Railway database offline/pausado")
            return False
    except Exception as e:
        print(f"❌ TCP ERRO: {e}")
        return False
    
    # TESTE 3: Conexão PostgreSQL
    print("\n🔍 TESTE 3: Conexão PostgreSQL")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            connect_timeout=15
        )
        
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print(f"✅ POSTGRESQL OK: {version[:50]}...")
        
        cursor.close()
        conn.close()
        
        print("🎉 RAILWAY POSTGRESQL 100% FUNCIONANDO!")
        return True
        
    except psycopg2.OperationalError as e:
        error_str = str(e)
        print(f"❌ POSTGRESQL FALHOU: {error_str}")
        
        if "Connection refused" in error_str:
            print("🔧 SOLUÇÃO: Verifique se o database está ativo no Railway")
        elif "timeout" in error_str:
            print("🔧 SOLUÇÃO: Problema de rede/firewall")
        elif "authentication" in error_str:
            print("🔧 SOLUÇÃO: Credenciais incorretas")
        
        return False
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        return False

def verificar_network_info():
    """Verificar informações de rede"""
    
    print("\n🌐 INFORMAÇÕES DE REDE")
    print("-" * 30)
    
    try:
        # IP público
        import requests
        ip_publico = requests.get('https://api.ipify.org', timeout=5).text
        print(f"📡 IP Público: {ip_publico}")
    except:
        print("📡 IP Público: Não detectado")
    
    # Testar conectividade geral
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('google.com', 80))
        sock.close()
        
        if result == 0:
            print("✅ Internet: OK")
        else:
            print("❌ Internet: Problema")
    except:
        print("❌ Internet: Erro no teste")

def testar_portas_alternativas():
    """Testar se outras portas Railway funcionam"""
    
    print("\n🔍 TESTE DE PORTAS ALTERNATIVAS")
    print("-" * 40)
    
    # Portas comuns do Railway
    portas_teste = [5432, 26257, 3306, 5433, 5434]
    host = "metro.proxy.rlwy.net"
    
    for porta in portas_teste:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, porta))
            sock.close()
            
            if result == 0:
                print(f"✅ Porta {porta}: Acessível")
            else:
                print(f"❌ Porta {porta}: Bloqueada")
        except:
            print(f"❌ Porta {porta}: Erro")

if __name__ == '__main__':
    print("🚨 DIAGNÓSTICO RAILWAY - SAMUEL")
    print("=" * 50)
    
    verificar_network_info()
    
    if not diagnostico_completo():
        print("\n🔧 TESTES ADICIONAIS:")
        testar_portas_alternativas()
        
        print("\n💡 SOLUÇÕES POSSÍVEIS:")
        print("1. Usar VPN se estiver em rede corporativa")
        print("2. Desativar temporariamente antivírus")
        print("3. Verificar se Railway database não foi pausado")
        print("4. Tentar de outro local/rede")
        print("5. Verificar credenciais no Railway Dashboard")
    
    print("\n" + "=" * 50)
