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

# CONFIGURAR ENCODING DO SISTEMA ANTES DE TUDO


def configurar_encoding():
    """Configurar encoding do sistema"""
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


# Executar configuração de encoding
configurar_encoding()

# CONFIGURAÇÃO FLEXÍVEL DE BANCO DE DADOS


def get_database_config():
    """Obter configuração do banco baseada no ambiente"""

    # Verificar se deve usar Railway
    environment = os.getenv('ENVIRONMENT', 'development')
    database_url = os.getenv('DATABASE_URL')

    if environment == 'production' or database_url:
        print("🌐 Configuração RAILWAY (Produção)")
        if database_url:
            return {'database_url': database_url}
        else:
            return {
                'host': os.getenv('RAILWAY_DB_HOST'),
                'database': os.getenv('RAILWAY_DB_NAME', 'railway'),
                'user': os.getenv('RAILWAY_DB_USER', 'postgres'),
                'password': os.getenv('RAILWAY_DB_PASSWORD'),
                'port': os.getenv('RAILWAY_DB_PORT', '5432'),
                'client_encoding': 'UTF8',
                'connect_timeout': 30
            }
    else:
        print("🏠 Configuração LOCAL (Desenvolvimento)")
        return {
            'host': os.getenv('LOCAL_DB_HOST', 'localhost'),
            'database': os.getenv('LOCAL_DB_NAME', 'designtex_db'),
            'user': os.getenv('LOCAL_DB_USER', 'postgres'),
            'password': os.getenv('LOCAL_DB_PASSWORD', 'samuca88'),
            'port': os.getenv('LOCAL_DB_PORT', '5432'),
            'client_encoding': 'UTF8',
            'connect_timeout': 30
        }


# Obter configuração do banco
DATABASE_CONFIG = get_database_config()


def conectar_postgresql():
    """Conectar ao PostgreSQL (local ou Railway)"""

    encodings_para_testar = ['UTF8', 'LATIN1', 'WIN1252', 'SQL_ASCII']

    for encoding in encodings_para_testar:
        try:
            print(f"🔄 Tentando conectar com encoding: {encoding}")

            # Se tiver DATABASE_URL (Railway), usar ela
            if 'database_url' in DATABASE_CONFIG:
                database_url = DATABASE_CONFIG['database_url']

                # Adicionar encoding na URL
                if '?' in database_url:
                    database_url += f'&client_encoding={encoding}'
                else:
                    database_url += f'?client_encoding={encoding}'

                conn = psycopg2.connect(database_url)

            else:
                # Usar configuração tradicional (local)
                config = DATABASE_CONFIG.copy()
                config['client_encoding'] = encoding
                conn = psycopg2.connect(**config)

            # Configurar encoding após conexão
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
                conn.close()
            continue

    print("❌ Não foi possível conectar com nenhum encoding")
    return None


def init_database():
    """Inicializar banco PostgreSQL com encoding seguro"""

    print("🔄 Inicializando PostgreSQL...")

    conn = conectar_postgresql()
    if not conn:
        print("❌ Falha na conexão inicial")
        return False

    try:
        cursor = conn.cursor()

        # Configurar encoding da sessão (modo compatível)
        try:
            cursor.execute("SET client_encoding TO 'SQL_ASCII';")
            cursor.execute("SET standard_conforming_strings TO on;")
            print("✅ Encoding da sessão configurado")
        except:
            print("⚠️  Usando encoding padrão do servidor")

        # Verificar se as tabelas já existem
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tabelas_existentes = cursor.fetchall()

        if tabelas_existentes:
            print(
                f"✅ Banco já inicializado com {len(tabelas_existentes)} tabelas")
            cursor.close()
            conn.close()
            return True

        # Criar tabelas com encoding seguro
        print("📋 Criando tabelas...")

        # Tabela clientes
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

        # Tabela pedidos
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

        # Tabela sequencia_pedidos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sequencia_pedidos (
                id INTEGER PRIMARY KEY DEFAULT 1,
                ultimo_numero INTEGER DEFAULT 0
            )
        """)

        # Inserir sequência inicial se não existir
        cursor.execute("""
            INSERT INTO sequencia_pedidos (id, ultimo_numero) 
            VALUES (1, 0) 
            ON CONFLICT (id) DO NOTHING
        """)

        # Tabelas de preços (estrutura básica)
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
    """Inserir dados iniciais com encoding seguro"""

    try:
        print("📋 Inserindo clientes iniciais...")

        # Clientes básicos (sem acentos para evitar problemas de encoding)
        clientes = [
            ('12.345.678/0001-90', 'EMPRESA ABC LTDA', 'EMPRESA ABC', '11999990001'),
            ('98.765.432/0001-10', 'COMERCIAL XYZ SA',
             'COMERCIAL XYZ', '11999990002'),
            ('11.222.333/0001-44', 'DISTRIBUIDORA 123 LTDA',
             'DISTRIBUIDORA 123', '11999990003')
        ]

        for cnpj, razao, fantasia, telefone in clientes:
            cursor.execute("""
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (cnpj) DO NOTHING
            """, (cnpj, razao, fantasia, telefone))

        conn.commit()
        print("✅ Clientes iniciais inseridos!")

        # Preços básicos
        print("📋 Inserindo preços iniciais...")

        precos = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150',
             'Tecido poliester 150D', 15.30, 14.60, 13.90, 13.50)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        conn.commit()
        print("✅ Preços iniciais inseridos!")

    except Exception as e:
        print(f"⚠️  Erro ao inserir dados iniciais: {e}")


def obter_proximo_numero_pedido():
    """Obter próximo número de pedido"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sequencia_pedidos SET ultimo_numero = ultimo_numero + 1 WHERE id = 1 RETURNING ultimo_numero")
        numero = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return str(numero).zfill(4)  # Formatar com zeros à esquerda
    except Exception as e:
        print(f"Erro ao obter número do pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None


def buscar_clientes():
    """Buscar todos os clientes"""
    conn = conectar_postgresql()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cnpj, razao_social, nome_fantasia FROM clientes ORDER BY razao_social")
        clientes = cursor.fetchall()
        cursor.close()
        conn.close()
        return clientes
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
        cursor.execute(
            "SELECT artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg FROM precos_normal ORDER BY artigo")
        precos = cursor.fetchall()
        cursor.close()
        conn.close()
        return precos
    except Exception as e:
        print(f"Erro ao buscar preços: {e}")
        if conn:
            conn.close()
        return []


def obter_proximo_numero_pedido_preview():
    """Obter próximo número de pedido (sem incrementar)"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ultimo_numero FROM sequencia_pedidos WHERE id = 1")
        numero = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return str(numero + 1).zfill(4)  # Próximo número
    except Exception as e:
        print(f"Erro ao obter número do pedido: {e}")
        if conn:
            conn.close()
        return None


def criar_pedido_completo(dados):
    """Criar pedido completo no banco"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Obter próximo número
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return None

        # Inserir pedido
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, representante, observacoes, valor_total)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            numero_pedido,
            dados['cnpj_cliente'],
            dados['representante'],
            dados.get('observacoes'),
            dados.get('valor_total', 0)
        ))

        pedido_id = cursor.fetchone()[0]
        conn.commit()

        cursor.close()
        conn.close()

        return {
            'id': pedido_id,
            'numero_pedido': numero_pedido
        }

    except Exception as e:
        print(f"Erro ao criar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None


def buscar_pedidos():
    """Buscar todos os pedidos"""
    conn = conectar_postgresql()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT numero_pedido, cnpj_cliente, representante, observacoes, valor_total, created_at
            FROM pedidos 
            ORDER BY created_at DESC
        """)
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()
        return pedidos
    except Exception as e:
        print(f"Erro ao buscar pedidos: {e}")
        if conn:
            conn.close()
        return []


# FLASK APP
app = Flask(__name__)


@app.route('/')
def home():
    """Página inicial"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DESIGNTEX TECIDOS - PostgreSQL</title>
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
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 25px;
            margin: 10px;
            transition: all 0.3s ease;
            font-weight: bold;
            font-size: 16px;
        }
        .btn:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        .btn-primary {
            background: #28a745;
            font-size: 18px;
            padding: 18px 35px;
        }
        .btn-primary:hover {
            background: #218838;
        }
        .actions {
            margin: 30px 0;
        }
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
        <p class="subtitle">Sistema de Pedidos - PostgreSQL</p>
        
        <div class="status">
            ✅ PostgreSQL Conectado e Funcionando
        </div>
        
        <div class="actions">
            <a href="/novo-pedido" class="btn btn-primary">➕ NOVO PEDIDO</a>
            <br>
            <a href="/pedidos" class="btn">📋 Ver Pedidos</a>
            <a href="/clientes" class="btn">👥 Ver Clientes</a>
            <a href="/precos" class="btn">💰 Ver Preços</a>
            <a href="/health" class="btn">🔍 Health Check</a>
        </div>
        
        <div class="info">
            <h3>📋 Sistema Completo de Pedidos:</h3>
            <ul class="endpoints">
                <li><code>POST /api/pedidos</code> - Criar novo pedido</li>
                <li><code>GET /pedidos</code> - Lista de pedidos</li>
                <li><code>GET /novo-pedido</code> - Formulário novo pedido</li>
                <li><code>GET /clientes</code> - Lista de clientes</li>
                <li><code>GET /precos</code> - Tabela de preços</li>
                <li><code>GET /health</code> - Status do sistema</li>
            </ul>
        </div>
        
        <div class="info">
            <h3>🔧 Para Power BI:</h3>
            <p>Use esta URL como fonte de dados:</p>
            <code style="background: #2d5f2d; color: white; padding: 8px; border-radius: 4px; display: block; margin-top: 10px;">
                http://127.0.0.1:5001
            </code>
        </div>
    </div>
</body>
</html>
    ''')


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
                'database': 'Railway PostgreSQL - Conectado',
                'version': version[:50],
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
    """Listar clientes em JSON"""
    clientes = buscar_clientes()
    clientes_json = []

    for cliente in clientes:
        clientes_json.append({
            'cnpj': cliente[0],
            'razao_social': cliente[1],
            'nome_fantasia': cliente[2]
        })

    return jsonify({
        'clientes': clientes_json,
        'total': len(clientes_json),
        'source': 'Railway PostgreSQL'
    })


@app.route('/precos')
def listar_precos():
    """Listar preços em JSON"""
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
        'total': len(precos_json),
        'source': 'Railway PostgreSQL'
    })


@app.route('/pedidos', methods=['POST'])
def criar_pedido():
    """Criar novo pedido"""
    try:
        data = request.get_json()

        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return jsonify({'error': 'Erro ao gerar número do pedido'}), 500

        conn = conectar_postgresql()
        if not conn:
            return jsonify({'error': 'Erro de conexão com banco'}), 500

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, representante, observacoes, valor_total)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            numero_pedido,
            data.get('cnpj_cliente'),
            data.get('representante'),
            data.get('observacoes'),
            data.get('valor_total', 0)
        ))

        pedido_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'pedido_id': pedido_id,
            'numero_pedido': numero_pedido,
            'message': 'Pedido criado com sucesso!'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/novo-pedido')
def formulario_pedido():
    """Página para criar novo pedido"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Novo Pedido - DESIGNTEX</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2em;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #333;
            font-weight: bold;
        }
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        input:focus, select:focus, textarea:focus {
            border-color: #667eea;
            outline: none;
        }
        .btn {
            background: #667eea;
            color: white;
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover {
            background: #5a6fd8;
        }
        .btn-secondary {
            background: #6c757d;
            text-decoration: none;
            display: inline-block;
            text-align: center;
            margin-right: 10px;
            width: 48%;
        }
        .btn-primary {
            width: 48%;
        }
        .button-group {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
        }
        .info {
            background: #e8f5e8;
            color: #2d5f2d;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
        #numero-pedido {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏭 NOVO PEDIDO - DESIGNTEX</h1>
        
        <div class="info">
            <p>Número do Pedido: <span id="numero-pedido">Carregando...</span></p>
        </div>
        
        <form id="form-pedido" onsubmit="criarPedido(event)">
            <div class="form-group">
                <label for="cliente">Cliente:</label>
                <select id="cliente" name="cliente" required>
                    <option value="">Selecione um cliente...</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="representante">Representante:</label>
                <input type="text" id="representante" name="representante" 
                       placeholder="Nome do representante" required>
            </div>
            
            <div class="form-group">
                <label for="observacoes">Observações:</label>
                <textarea id="observacoes" name="observacoes" rows="4" 
                          placeholder="Observações do pedido (opcional)"></textarea>
            </div>
            
            <div class="button-group">
                <a href="/" class="btn btn-secondary">🏠 Voltar</a>
                <button type="submit" class="btn btn-primary">💾 Criar Pedido</button>
            </div>
        </form>
    </div>

    <script>
        // Carregar número do próximo pedido
        async function carregarNumeroPedido() {
            try {
                const response = await fetch('/api/proximo-numero');
                const data = await response.json();
                document.getElementById('numero-pedido').textContent = data.numero;
            } catch (error) {
                document.getElementById('numero-pedido').textContent = 'Erro';
            }
        }
        
        // Carregar lista de clientes
        async function carregarClientes() {
            try {
                const response = await fetch('/clientes');
                const data = await response.json();
                const select = document.getElementById('cliente');
                
                data.clientes.forEach(cliente => {
                    const option = document.createElement('option');
                    option.value = cliente.cnpj;
                    option.textContent = `${cliente.razao_social} (${cliente.cnpj})`;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Erro ao carregar clientes:', error);
            }
        }
        
        // Criar pedido
        async function criarPedido(event) {
            event.preventDefault();
            
            const formData = new FormData(event.target);
            const pedido = {
                cnpj_cliente: formData.get('cliente'),
                representante: formData.get('representante'),
                observacoes: formData.get('observacoes') || null,
                valor_total: 0  // Por enquanto zerado
            };
            
            try {
                const response = await fetch('/api/pedidos', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(pedido)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert(`✅ Pedido ${result.numero_pedido} criado com sucesso!`);
                    window.location.href = '/pedidos';
                } else {
                    alert(`❌ Erro: ${result.error}`);
                }
            } catch (error) {
                alert(`❌ Erro ao criar pedido: ${error.message}`);
            }
        }
        
        // Carregar dados quando a página carregar
        document.addEventListener('DOMContentLoaded', function() {
            carregarNumeroPedido();
            carregarClientes();
        });
    </script>
</body>
</html>
    ''')


@app.route('/api/proximo-numero')
def api_proximo_numero():
    """API para obter próximo número de pedido"""
    numero = obter_proximo_numero_pedido_preview()
    if numero:
        return jsonify({'numero': numero})
    else:
        return jsonify({'error': 'Erro ao obter número'}), 500


@app.route('/api/pedidos', methods=['POST'])
def api_criar_pedido():
    """API para criar novo pedido"""
    try:
        dados = request.get_json()

        # Validar dados obrigatórios
        if not dados.get('cnpj_cliente'):
            return jsonify({'error': 'CNPJ do cliente é obrigatório'}), 400

        if not dados.get('representante'):
            return jsonify({'error': 'Representante é obrigatório'}), 400

        # Criar pedido
        resultado = criar_pedido_completo(dados)

        if resultado:
            return jsonify({
                'success': True,
                'numero_pedido': resultado['numero_pedido'],
                'message': 'Pedido criado com sucesso!'
            })
        else:
            return jsonify({'error': 'Erro ao criar pedido'}), 500

    except Exception as e:
        print(f"Erro ao criar pedido: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/pedidos')
def listar_pedidos_page():
    """Página para listar pedidos"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lista de Pedidos - DESIGNTEX</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        .actions {
            display: flex;
            justify-content: space-between;
            margin-bottom: 30px;
        }
        .btn {
            background: #667eea;
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
            font-weight: bold;
        }
        .btn:hover { background: #5a6fd8; }
        .btn-secondary { background: #6c757d; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f8f9fa;
            color: #333;
            font-weight: bold;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .status-loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .pedido-numero {
            font-weight: bold;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 LISTA DE PEDIDOS - DESIGNTEX</h1>
        
        <div class="actions">
            <a href="/" class="btn btn-secondary">🏠 Home</a>
            <a href="/novo-pedido" class="btn">➕ Novo Pedido</a>
        </div>
        
        <div id="tabela-pedidos">
            <div class="status-loading">🔄 Carregando pedidos...</div>
        </div>
    </div>

    <script>
        async function carregarPedidos() {
            try {
                const response = await fetch('/api/pedidos-lista');
                const data = await response.json();
                
                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Número</th>
                                <th>Cliente</th>
                                <th>Representante</th>
                                <th>Valor Total</th>
                                <th>Data</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                if (data.pedidos && data.pedidos.length > 0) {
                    data.pedidos.forEach(pedido => {
                        html += `
                            <tr>
                                <td><span class="pedido-numero">${pedido.numero_pedido}</span></td>
                                <td>${pedido.cnpj_cliente}</td>
                                <td>${pedido.representante}</td>
                                <td>R$ ${(pedido.valor_total || 0).toFixed(2)}</td>
                                <td>${new Date(pedido.created_at).toLocaleDateString('pt-BR')}</td>
                                <td>
                                    <a href="/pedido/${pedido.numero_pedido}" class="btn" style="padding: 5px 10px; font-size: 12px;">👁️ Ver</a>
                                </td>
                            </tr>
                        `;
                    });
                } else {
                    html += `
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 40px; color: #666;">
                                📝 Nenhum pedido encontrado
                                <br><br>
                                <a href="/novo-pedido" class="btn">➕ Criar Primeiro Pedido</a>
                            </td>
                        </tr>
                    `;
                }
                
                html += `
                        </tbody>
                    </table>
                `;
                
                document.getElementById('tabela-pedidos').innerHTML = html;
                
            } catch (error) {
                document.getElementById('tabela-pedidos').innerHTML = `
                    <div class="status-loading">❌ Erro ao carregar pedidos: ${error.message}</div>
                `;
            }
        }
        
        // Carregar pedidos quando a página carregar
        document.addEventListener('DOMContentLoaded', carregarPedidos);
    </script>
</body>
</html>
    ''')


@app.route('/api/pedidos-lista')
def api_listar_pedidos():
    """API para listar pedidos"""
    pedidos = buscar_pedidos()
    pedidos_json = []

    for pedido in pedidos:
        pedidos_json.append({
            'numero_pedido': pedido[0],
            'cnpj_cliente': pedido[1],
            'representante': pedido[2],
            'observacoes': pedido[3],
            'valor_total': float(pedido[4]) if pedido[4] else 0,
            'created_at': pedido[5].isoformat() if pedido[5] else None
        })

    return jsonify({
        'pedidos': pedidos_json,
        'total': len(pedidos_json)
    })


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Railway PostgreSQL")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/precos")
        print("-" * 50)

        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
