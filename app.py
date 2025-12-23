import os
import sys
import locale
import psycopg2
from flask import Flask, render_template_string, request, jsonify, send_file
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import io
import json

# CONFIGURAR ENCODING DO SISTEMA
def configurar_encoding():
    """Configurar encoding do sistema"""
    try:
        if sys.platform.startswith('win'):
            os.system('chcp 65001 > nul')
        
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PGCLIENTENCODING'] = 'UTF8'
        
        try:
            locale.setlocale(locale.LC_ALL, 'C')
        except:
            pass
            
        print("✅ Encoding configurado com sucesso")
    except Exception as e:
        print(f"⚠️  Aviso na configuração de encoding: {e}")

configurar_encoding()

# CONFIGURAÇÃO FLEXÍVEL DE AMBIENTE
def get_database_config():
    """Obter configuração do banco baseada no ambiente"""
    
    # Railway sempre tem DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        print("🌐 Usando DATABASE_URL do Railway")
        return {'database_url': database_url}
    
    # Ambiente de desenvolvimento (local)
    environment = os.getenv('ENVIRONMENT', 'development')
    railway_env = os.getenv('RAILWAY_ENVIRONMENT_NAME')
    
    if environment == 'production' or railway_env:
        print("🚀 Configuração RAILWAY (Produção)")
        # Fallback para variáveis individuais se não tiver DATABASE_URL
        return {
            'host': os.getenv('PGHOST', 'localhost'),
            'database': os.getenv('PGDATABASE', 'railway'),
            'user': os.getenv('PGUSER', 'postgres'),
            'password': os.getenv('PGPASSWORD'),
            'port': os.getenv('PGPORT', '5432'),
            'client_encoding': 'UTF8',
            'connect_timeout': 30
        }
    else:
        print("🏠 Configuração LOCAL (Desenvolvimento)")
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'designtex_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'samuca88'),
            'port': os.getenv('DB_PORT', '5432'),
            'client_encoding': 'UTF8',
            'connect_timeout': 30
        }

DATABASE_CONFIG = get_database_config()

def conectar_postgresql():
    """Conectar ao PostgreSQL (local ou Railway)"""
    
    encodings_para_testar = ['UTF8', 'LATIN1', 'SQL_ASCII']
    
    for encoding in encodings_para_testar:
        try:
            print(f"🔄 Tentando conectar com encoding: {encoding}")
            
            if 'database_url' in DATABASE_CONFIG:
                # Railway com DATABASE_URL
                database_url = DATABASE_CONFIG['database_url']
                
                # Adicionar encoding na URL se necessário
                if '?' in database_url:
                    database_url += f'&client_encoding={encoding}'
                else:
                    database_url += f'?client_encoding={encoding}'
                
                conn = psycopg2.connect(database_url)
            else:
                # Local com configuração individual
                config = DATABASE_CONFIG.copy()
                config['client_encoding'] = encoding
                conn = psycopg2.connect(**config)
            
            conn.set_client_encoding(encoding)
            
            # Testar conexão
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            resultado = cursor.fetchone()
            cursor.close()
            
            print(f"✅ Conectado com sucesso usando encoding: {encoding}")
            print(f"📋 PostgreSQL: {str(resultado[0])[:60]}...")
            
            return conn
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Erro com encoding {encoding}: {error_msg[:80]}...")
            if 'conn' in locals():
                try:
                    conn.close()
                except:
                    pass
            continue
    
    print("❌ Não foi possível conectar com nenhum encoding")
    return None

def init_database():
    """Inicializar banco PostgreSQL"""
    
    print("🔄 Inicializando PostgreSQL...")
    
    conn = conectar_postgresql()
    if not conn:
        print("❌ Falha na conexão inicial")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Configurar encoding da sessão
        try:
            cursor.execute("SET client_encoding TO 'UTF8';")
            cursor.execute("SET standard_conforming_strings TO on;")
            print("✅ Encoding da sessão configurado")
        except:
            print("⚠️  Usando encoding padrão do servidor")
        
        # Verificar tabelas existentes
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tabelas_existentes = cursor.fetchall()
        
        if tabelas_existentes:
            print(f"✅ Banco já inicializado com {len(tabelas_existentes)} tabelas")
            cursor.close()
            conn.close()
            return True
        
        print("📋 Criando tabelas...")
        
        # Tabela clientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                cnpj VARCHAR(18) UNIQUE NOT NULL,
                razao_social VARCHAR(200) NOT NULL,
                nome_fantasia VARCHAR(150),
                telefone VARCHAR(20),
                email VARCHAR(100),
                endereco VARCHAR(200),
                cidade VARCHAR(100),
                estado VARCHAR(2),
                cep VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela pedidos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                nome_representante VARCHAR(100) NOT NULL,
                cnpj_cliente VARCHAR(18) NOT NULL,
                razao_social_cliente VARCHAR(200) NOT NULL,
                telefone_cliente VARCHAR(20),
                prazo_pagamento VARCHAR(50),
                tipo_pedido VARCHAR(20) CHECK (tipo_pedido IN ('OP', 'PE')),
                numero_op VARCHAR(50),
                tipo_frete VARCHAR(10) CHECK (tipo_frete IN ('FOB', 'CIF')),
                transportadora_fob VARCHAR(100),
                transportadora_cif VARCHAR(100),
                venda_triangular VARCHAR(10) CHECK (venda_triangular IN ('Sim', 'Nao')),
                dados_triangulacao TEXT,
                regime_ret VARCHAR(10) CHECK (regime_ret IN ('Sim', 'Nao')),
                tipo_produto VARCHAR(20),
                tabela_precos VARCHAR(50),
                valor_total DECIMAL(12,2) DEFAULT 0.00,
                observacoes TEXT,
                status VARCHAR(20) DEFAULT 'ATIVO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela sequencia_pedidos
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
        
        # Tabelas de preços
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS precos_ld (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                icms_18_ld DECIMAL(10,2),
                icms_12_ld DECIMAL(10,2),
                icms_7_ld DECIMAL(10,2),
                ret_ld_mg DECIMAL(10,2)
            )
        """)
        
        conn.commit()
        print("✅ Tabelas PostgreSQL criadas com sucesso!")
        
        # Inserir dados iniciais
        inserir_dados_iniciais(cursor, conn)
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao inicializar database: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def inserir_dados_iniciais(cursor, conn):
    """Inserir dados iniciais"""
    
    try:
        print("📋 Inserindo dados iniciais...")
        
        # Clientes de exemplo
        clientes = [
            ('12.345.678/0001-90', 'EMPRESA ABC LTDA', 'EMPRESA ABC', '11999990001'),
            ('98.765.432/0001-10', 'COMERCIAL XYZ SA', 'COMERCIAL XYZ', '11999990002'),
            ('11.222.333/0001-44', 'DISTRIBUIDORA 123 LTDA', 'DISTRIBUIDORA 123', '11999990003'),
            ('22.333.444/0001-55', 'CONFECCOES PAULO LTDA', 'CONFECCOES PAULO', '11999990004'),
            ('33.444.555/0001-66', 'TEXTIL MODERNA SA', 'TEXTIL MODERNA', '11999990005')
        ]
        
        for cnpj, razao, fantasia, telefone in clientes:
            cursor.execute("""
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (cnpj) DO NOTHING
            """, (cnpj, razao, fantasia, telefone))
        
        # Preços normais
        precos_normal = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado', 12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D microfibra', 15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 40/1', 'VIS401', 'Tecido viscose 40/1 lisa', 18.20, 17.40, 16.60, 16.20),
            ('COTTON 24/1', 'COT241', 'Tecido cotton 24/1 cardado', 14.80, 14.10, 13.40, 13.00),
            ('MODAL 50/1', 'MOD501', 'Tecido modal 50/1 premium', 22.50, 21.80, 21.10, 20.70)
        ]
        
        for artigo, codigo, desc, p18, p12, p7, ret in precos_normal:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))
        
        # Preços LD
        precos_ld = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado LD', 13.20, 12.50, 11.90, 11.50),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D microfibra LD', 16.00, 15.30, 14.60, 14.20),
            ('VISCOSE 40/1', 'VIS401', 'Tecido viscose 40/1 lisa LD', 19.00, 18.20, 17.40, 17.00),
            ('COTTON 24/1', 'COT241', 'Tecido cotton 24/1 cardado LD', 15.50, 14.80, 14.10, 13.70),
            ('MODAL 50/1', 'MOD501', 'Tecido modal 50/1 premium LD', 23.50, 22.80, 22.10, 21.70)
        ]
        
        for artigo, codigo, desc, p18, p12, p7, ret in precos_ld:
            cursor.execute("""
                INSERT INTO precos_ld (artigo, codigo, descricao, icms_18_ld, icms_12_ld, icms_7_ld, ret_ld_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))
        
        conn.commit()
        print("✅ Dados iniciais inseridos!")
        
    except Exception as e:
        print(f"⚠️  Erro ao inserir dados iniciais: {e}")

# FUNÇÕES AUXILIARES
def obter_proximo_numero_pedido():
    """Obter próximo número de pedido"""
    conn = conectar_postgresql()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE sequencia_pedidos SET ultimo_numero = ultimo_numero + 1 WHERE id = 1 RETURNING ultimo_numero")
        numero = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return str(numero).zfill(4)
    except Exception as e:
        print(f"Erro ao obter número do pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None

def buscar_clientes(query=''):
    """Buscar clientes"""
    conn = conectar_postgresql()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        if query:
            cursor.execute("""
                SELECT cnpj, razao_social, nome_fantasia, telefone 
                FROM clientes 
                WHERE UPPER(razao_social) LIKE UPPER(%s) 
                   OR UPPER(nome_fantasia) LIKE UPPER(%s)
                   OR cnpj LIKE %s
                ORDER BY razao_social 
                LIMIT 10
            """, (f'%{query}%', f'%{query}%', f'%{query}%'))
        else:
            cursor.execute("SELECT cnpj, razao_social, nome_fantasia, telefone FROM clientes ORDER BY razao_social")
        
        clientes = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [{'cnpj': c[0], 'razao_social': c[1], 'nome_fantasia': c[2], 'telefone': c[3]} for c in clientes]
    
    except Exception as e:
        print(f"Erro ao buscar clientes: {e}")
        if conn:
            conn.close()
        return []

def buscar_precos_normal():
    """Buscar preços normais"""
    conn = conectar_postgresql()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg FROM precos_normal ORDER BY artigo")
        precos = cursor.fetchall()
        cursor.close()
        conn.close()
        return precos
    except Exception as e:
        print(f"Erro ao buscar preços: {e}")
        if conn:
            conn.close()
        return []

def salvar_pedido(dados_pedido):
    """Salvar pedido no banco"""
    conn = conectar_postgresql()
    if not conn:
        return {'success': False, 'error': 'Erro de conexão com banco'}
    
    try:
        cursor = conn.cursor()
        
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return {'success': False, 'error': 'Erro ao gerar número do pedido'}
        
        cursor.execute("""
            INSERT INTO pedidos (
                numero_pedido, nome_representante, cnpj_cliente, razao_social_cliente,
                telefone_cliente, prazo_pagamento, tipo_pedido, numero_op, tipo_frete,
                transportadora_fob, transportadora_cif, venda_triangular, dados_triangulacao,
                regime_ret, tipo_produto, tabela_precos, valor_total, observacoes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            numero_pedido,
            dados_pedido.get('nomeRepresentante'),
            dados_pedido.get('cnpj'),
            dados_pedido.get('razaoSocial'),
            dados_pedido.get('telefone'),
            dados_pedido.get('prazoPagamento'),
            dados_pedido.get('tipoPedido'),
            dados_pedido.get('numeroOP'),
            dados_pedido.get('tipoFrete'),
            dados_pedido.get('transportadoraFOB'),
            dados_pedido.get('transportadoraCIF'),
            dados_pedido.get('vendaTriangular'),
            dados_pedido.get('dadosTriangulacao'),
            dados_pedido.get('regimeRET'),
            dados_pedido.get('tipoProduto'),
            dados_pedido.get('tabelaPrecos'),
            dados_pedido.get('valorTotal', 0),
            dados_pedido.get('observacoes')
        ))
        
        pedido_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return {'success': True, 'numero_pedido': numero_pedido}
    
    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': str(e)}

# FLASK APP
app = Flask(__name__)

@app.route('/')
def home():
    """Página inicial"""
    railway_env = os.getenv('RAILWAY_ENVIRONMENT_NAME')
    ambiente = "🌐 PRODUÇÃO (Railway)" if railway_env else "🏠 DESENVOLVIMENTO"
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DESIGNTEX TECIDOS - Sistema de Pedidos</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 600px;
            width: 90%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .status {
            background: #e8f5e8;
            color: #2d5f2d;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            font-weight: bold;
        }
        .btn {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 25px;
            margin: 5px;
            transition: all 0.3s ease;
            font-weight: bold;
        }
        .btn:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        .btn.success { background: #28a745; }
        .btn.info { background: #17a2b8; }
        .btn.warning { background: #ffc107; color: #333; }
        .info {
            background: #f8f9ff;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
            text-align: left;
        }
        .info h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .endpoints {
            list-style: none;
            padding: 0;
        }
        .endpoints li {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .endpoints li:last-child {
            border-bottom: none;
        }
        .endpoints code {
            background: #667eea;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏭 DESIGNTEX TECIDOS</h1>
        <p class="subtitle">Sistema de Pedidos de Vendas</p>
        
        <div class="status">
            ✅ PostgreSQL Conectado - {{ ambiente }}
        </div>
        
        <a href="/health" class="btn">🔍 Health Check</a>
        <a href="/clientes" class="btn">👥 Clientes</a>
        <a href="/precos" class="btn">💰 Preços</a>
        <a href="/novo-pedido" class="btn success">📋 Novo Pedido</a>
        
        <div class="info">
            <h3>📋 Endpoints API:</h3>
            <ul class="endpoints">
                <li><code>GET /health</code> - Status do sistema</li>
                <li><code>GET /clientes</code> - Lista de clientes</li>
                <li><code>GET /precos</code> - Tabela de preços</li>
                <li><code>GET /novo-pedido</code> - Formulário de pedidos</li>
            </ul>
        </div>
    </div>
</body>
</html>
    ''', ambiente=ambiente)

@app.route('/health')
def health():
    """Health check endpoint"""
    conn = conectar_postgresql()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return jsonify({
                'status': 'OK',
                'database': 'PostgreSQL - Conectado',
                'version': version[:60],
                'environment': os.getenv('RAILWAY_ENVIRONMENT_NAME', 'development'),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({
                'status': 'ERROR',
                'database': f'Erro: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }), 500
    else:
        return jsonify({
            'status': 'ERROR',
            'database': 'PostgreSQL - Desconectado',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/clientes')
def listar_clientes():
    """Listar clientes"""
    clientes = buscar_clientes()
    return jsonify({
        'clientes': clientes,
        'total': len(clientes)
    })

@app.route('/precos')
def listar_precos():
    """Listar preços"""
    precos = buscar_precos_normal()
    precos_json = []
    
    for preco in precos:
        precos_json.append({
            'artigo': preco[0],
            'codigo': preco[1],
            'descricao': preco[2],
            'icms_18': float(preco[3]) if preco[3] else 0,
            'icms_12': float(preco[4]) if preco[4] else 0,
            'icms_7': float(preco[5]) if preco[5] else 0,
            'ret_mg': float(preco[6]) if preco[6] else 0
        })
    
    return jsonify({
        'precos': precos_json,
        'total': len(precos_json)
    })

@app.route('/api/buscar_clientes')
def api_buscar_clientes():
    """API para buscar clientes (autocomplete)"""
    query = request.args.get('q', '')
    clientes = buscar_clientes(query)
    return jsonify(clientes)

@app.route('/novo-pedido')
def novo_pedido():
    """Página do formulário de pedidos"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Novo Pedido - Designtex Tecidos</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .container { margin-top: 20px; }
        .btn-home { margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="btn btn-secondary btn-home">← Voltar</a>
        
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h4>📋 Novo Pedido de Vendas</h4>
            </div>
            <div class="card-body">
                <form id="pedidoForm">
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label class="form-label">Representante *</label>
                            <input type="text" class="form-control" id="representante" required>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">CNPJ Cliente *</label>
                            <input type="text" class="form-control" id="cnpj" required>
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-12">
                            <label class="form-label">Razão Social *</label>
                            <input type="text" class="form-control" id="razaoSocial" required>
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label class="form-label">Telefone</label>
                            <input type="text" class="form-control" id="telefone">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Valor Total</label>
                            <input type="number" class="form-control" id="valorTotal" step="0.01">
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Observações</label>
                        <textarea class="form-control" id="observacoes" rows="3"></textarea>
                    </div>
                    
                    <button type="submit" class="btn btn-primary">💾 Salvar Pedido</button>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.getElementById('pedidoForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const dados = {
                nomeRepresentante: document.getElementById('representante').value,
                cnpj: document.getElementById('cnpj').value,
                razaoSocial: document.getElementById('razaoSocial').value,
                telefone: document.getElementById('telefone').value,
                valorTotal: parseFloat(document.getElementById('valorTotal').value) || 0,
                observacoes: document.getElementById('observacoes').value
            };
            
            fetch('/submit_pedido', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(dados)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`✅ Sucesso! Pedido ${data.numero_pedido} criado!`);
                    document.getElementById('pedidoForm').reset();
                } else {
                    alert(`❌ Erro: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('Erro:', error);
                alert('❌ Erro ao enviar pedido');
            });
        });
    </script>
</body>
</html>
    ''')

@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Processar envio de pedido"""
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'success': False, 'message': 'Dados não recebidos'})
        
        resultado = salvar_pedido(dados)
        
        if resultado['success']:
            return jsonify({
                'success': True,
                'message': 'Pedido criado com sucesso!',
                'numero_pedido': resultado['numero_pedido']
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado['error']
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        })

# CONFIGURAÇÃO DE PORTA
def get_port():
    """Obter porta do ambiente"""
    return int(os.getenv('PORT', 5001))

if __name__ == '__main__':
    # Inicializar banco
    if init_database():
        port = get_port()
        
        # Detectar se está no Railway
        if os.getenv('RAILWAY_ENVIRONMENT_NAME'):
            print("🌐 RODANDO NO RAILWAY")
            app.run(host='0.0.0.0', port=port, debug=False)
        else:
            print("🏠 RODANDO LOCALMENTE")
            print(f"📡 Servidor: http://127.0.0.1:{port}")
            app.run(host='127.0.0.1', port=port, debug=True)
    else:
        print("❌ Falha na inicialização do banco")
