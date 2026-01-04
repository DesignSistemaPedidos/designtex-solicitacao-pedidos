import os
import sys
import locale
import psycopg2
from flask import Flask, render_template_string, request, jsonify
from datetime import datetime

# FORÇAR CONFIGURAÇÃO RAILWAY
os.environ['ENVIRONMENT'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway'

# CONFIGURAR ENCODING
def configurar_encoding():
    try:
        if sys.platform.startswith('win'):
            os.system('chcp 65001 > nul')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PGCLIENTENCODING'] = 'SQL_ASCII'
        try:
            locale.setlocale(locale.LC_ALL, 'C')
        except:
            pass
        print("✅ Encoding configurado com sucesso")
    except Exception as e:
        print(f"⚠️  Aviso na configuração de encoding: {e}")

configurar_encoding()

def conectar_railway():
    """Conectar especificamente ao Railway"""
    
    database_url = "postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway"
    encodings = ['UTF8', 'LATIN1', 'SQL_ASCII']
    
    print("🌐 TESTANDO CONEXÃO RAILWAY")
    print("-" * 40)
    
    for encoding in encodings:
        try:
            print(f"🔄 Tentando encoding: {encoding}")
            
            url_com_encoding = f"{database_url}?client_encoding={encoding}&connect_timeout=30"
            
            conn = psycopg2.connect(url_com_encoding)
            conn.set_client_encoding(encoding)
            
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            resultado = cursor.fetchone()
            cursor.close()
            
            print(f"✅ Railway conectado com {encoding}!")
            print(f"📋 Version: {str(resultado[0])[:50]}...")
            
            return conn
            
        except Exception as e:
            print(f"❌ Falhou {encoding}: {str(e)[:60]}...")
            if 'conn' in locals():
                conn.close()
            continue
    
    print("❌ Railway não conectou com nenhum encoding")
    return None

def init_railway_database():
    """Inicializar tabelas no Railway"""
    
    print("🔄 Inicializando Railway Database...")
    
    conn = conectar_railway()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Verificar tabelas existentes
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tabelas = cursor.fetchall()
        
        if tabelas:
            print(f"✅ Railway já tem {len(tabelas)} tabelas")
            cursor.close()
            conn.close()
            return True
        
        print("📋 Criando tabelas no Railway...")
        
        # Criar tabelas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                cnpj VARCHAR(18) UNIQUE NOT NULL,
                razao_social VARCHAR(200) NOT NULL,
                nome_fantasia VARCHAR(150),
                telefone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                representante VARCHAR(100),
                observacoes TEXT,
                valor_total DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sequencia_pedidos (
                id INTEGER PRIMARY KEY DEFAULT 1,
                ultimo_numero INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            INSERT INTO sequencia_pedidos (id, ultimo_numero) 
            VALUES (1, 0) 
            ON CONFLICT (id) DO NOTHING
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS precos_normal (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                icms_18 DECIMAL(10,2),
                icms_12 DECIMAL(10,2),
                icms_7 DECIMAL(10,2),
                ret_mg DECIMAL(10,2)
            )
        """)
        
        conn.commit()
        print("✅ Tabelas Railway criadas!")
        
        # Inserir dados iniciais
        print("📋 Inserindo dados iniciais...")
        
        clientes = [
            ('12.345.678/0001-90', 'EMPRESA ABC LTDA', 'EMPRESA ABC', '11999990001'),
            ('98.765.432/0001-10', 'COMERCIAL XYZ SA', 'COMERCIAL XYZ', '11999990002'),
            ('11.222.333/0001-44', 'DISTRIBUIDORA 123 LTDA', 'DISTRIBUIDORA 123', '11999990003')
        ]
        
        for cnpj, razao, fantasia, telefone in clientes:
            cursor.execute("""
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (cnpj) DO NOTHING
            """, (cnpj, razao, fantasia, telefone))
        
        precos = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1', 12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D', 15.30, 14.60, 13.90, 13.50)
        ]
        
        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))
        
        conn.commit()
        print("✅ Dados inseridos no Railway!")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro Railway: {e}")
        if conn:
            conn.close()
        return False

# FLASK APP SIMPLES PARA TESTAR RAILWAY
app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string('''
    <h1>🌐 DESIGNTEX - RAILWAY TEST</h1>
    <p>✅ Conectado ao Railway PostgreSQL</p>
    <a href="/health">Health Check</a> | 
    <a href="/clientes">Clientes</a> | 
    <a href="/precos">Preços</a>
    ''')

@app.route('/health')
def health():
    conn = conectar_railway()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return jsonify({
                'status': 'OK',
                'database': 'Railway PostgreSQL',
                'version': version[:60],
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'status': 'ERROR', 'error': str(e)}), 500
    else:
        return jsonify({'status': 'ERROR', 'error': 'Não conectou'}), 500

@app.route('/clientes')
def clientes():
    conn = conectar_railway()
    if not conn:
        return jsonify({'error': 'Sem conexão'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT cnpj, razao_social, nome_fantasia FROM clientes ORDER BY razao_social")
        results = cursor.fetchall()
        
        clientes_list = []
        for r in results:
            clientes_list.append({
                'cnpj': r[0],
                'razao_social': r[1], 
                'nome_fantasia': r[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({'clientes': clientes_list, 'total': len(clientes_list)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if init_railway_database():
        print("🚀 SERVIDOR RAILWAY FUNCIONANDO!")
        print("📡 http://127.0.0.1:5002")
        app.run(host='0.0.0.0', port=5002, debug=False)  # SEM DEBUG!
    else:
        print("❌ Falhou Railway")
