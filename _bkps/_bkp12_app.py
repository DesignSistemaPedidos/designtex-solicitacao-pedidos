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

        # Tabela itens_pedido
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10),
                artigo VARCHAR(100),
                quantidade INTEGER,
                preco_unitario DECIMAL(10,2),
                preco_total DECIMAL(10,2),
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
             'DISTRIBUIDORA 123', '11999990003'),
            ('22.333.444/0001-55', 'TEXTIL BRASIL SA',
             'TEXTIL BRASIL', '11999990004'),
            ('33.444.555/0001-66', 'MODA & CIA LTDA', 'MODA & CIA', '11999990005')
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
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D texturizado',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 30/1', 'VIS301', 'Tecido viscose 30/1 premium',
             18.20, 17.40, 16.80, 16.20),
            ('ALGODAO 24/1', 'ALG241', 'Tecido algodao 24/1 cardado',
             14.80, 14.20, 13.60, 13.10),
            ('POLIAMIDA 40D', 'POL40D', 'Tecido poliamida 40 denier',
             22.50, 21.80, 21.20, 20.60)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        conn.commit()
        print("✅ Preços iniciais inseridos!")

        # Preços LD
        precos_ld = [
            ('ALGODAO 30/1 LD', 'ALG301LD',
             'Tecido algodao 30/1 linha diferenciada', 13.80, 13.10, 12.50, 12.20),
            ('POLIESTER 150D LD', 'POL150LD',
             'Tecido poliester 150D linha diferenciada', 16.90, 16.20, 15.50, 15.10)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos_ld:
            cursor.execute("""
                INSERT INTO precos_ld (artigo, codigo, descricao, icms_18_ld, icms_12_ld, icms_7_ld, ret_ld_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        conn.commit()
        print("✅ Preços LD inseridos!")

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


def buscar_precos_ld():
    """Buscar preços LD"""
    conn = conectar_postgresql()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT artigo, codigo, descricao, icms_18_ld, icms_12_ld, icms_7_ld, ret_ld_mg FROM precos_ld ORDER BY artigo")
        precos = cursor.fetchall()
        cursor.close()
        conn.close()
        return precos
    except Exception as e:
        print(f"Erro ao buscar preços LD: {e}")
        if conn:
            conn.close()
        return []


def salvar_pedido(numero_pedido, cnpj_cliente, representante, observacoes, itens, valor_total):
    """Salvar pedido no banco"""
    conn = conectar_postgresql()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Inserir pedido
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, representante, observacoes, valor_total)
            VALUES (%s, %s, %s, %s, %s)
        """, (numero_pedido, cnpj_cliente, representante, observacoes, valor_total))

        # Inserir itens
        for item in itens:
            cursor.execute("""
                INSERT INTO itens_pedido (numero_pedido, artigo, quantidade, preco_unitario, preco_total)
                VALUES (%s, %s, %s, %s, %s)
            """, (numero_pedido, item['artigo'], item['quantidade'], item['preco_unitario'], item['preco_total']))

        conn.commit()
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def buscar_pedido(numero_pedido):
    """Buscar pedido pelo número"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Buscar dados do pedido
        cursor.execute("""
            SELECT p.numero_pedido, p.cnpj_cliente, c.razao_social, c.nome_fantasia, 
                   p.representante, p.observacoes, p.valor_total, p.created_at
            FROM pedidos p
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj
            WHERE p.numero_pedido = %s
        """, (numero_pedido,))

        pedido = cursor.fetchone()
        if not pedido:
            cursor.close()
            conn.close()
            return None

        # Buscar itens do pedido
        cursor.execute("""
            SELECT artigo, quantidade, preco_unitario, preco_total
            FROM itens_pedido
            WHERE numero_pedido = %s
            ORDER BY id
        """, (numero_pedido,))

        itens = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            'numero_pedido': pedido[0],
            'cnpj_cliente': pedido[1],
            'razao_social': pedido[2],
            'nome_fantasia': pedido[3],
            'representante': pedido[4],
            'observacoes': pedido[5],
            'valor_total': float(pedido[6]) if pedido[6] else 0,
            'created_at': pedido[7],
            'itens': [{'artigo': item[0], 'quantidade': item[1],
                      'preco_unitario': float(item[2]), 'preco_total': float(item[3])}
                      for item in itens]
        }

    except Exception as e:
        print(f"Erro ao buscar pedido: {e}")
        if conn:
            conn.close()
        return None


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
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 25px;
            margin: 8px;
            transition: all 0.3s ease;
            font-weight: bold;
            font-size: 14px;
        }
        .btn:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        .btn.secondary {
            background: #28a745;
        }
        .btn.secondary:hover {
            background: #218838;
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
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏭 DESIGNTEX TECIDOS</h1>
        <p class="subtitle">Sistema de Pedidos - PostgreSQL Railway</p>
        
        <div class="status">
            ✅ PostgreSQL Railway Conectado e Funcionando
        </div>
        
        <div class="grid">
            <a href="/health" class="btn">🔍 Health Check</a>
            <a href="/clientes" class="btn">👥 Clientes</a>
            <a href="/precos" class="btn">💰 Preços Normal</a>
            <a href="/precos-ld" class="btn secondary">💎 Preços LD</a>
            <a href="/pedidos" class="btn secondary">📋 Listar Pedidos</a>
        </div>
        
        <div class="info">
            <h3>📋 APIs Disponíveis:</h3>
            <ul class="endpoints">
                <li><code>GET /health</code> - Status do sistema</li>
                <li><code>GET /clientes</code> - Lista de clientes</li>
                <li><code>GET /precos</code> - Tabela preços normal</li>
                <li><code>GET /precos-ld</code> - Tabela preços LD</li>
                <li><code>POST /criar-pedido</code> - Criar novo pedido</li>
                <li><code>GET /pedidos</code> - Listar todos pedidos</li>
                <li><code>GET /pedido/{numero}</code> - Buscar pedido</li>
                <li><code>GET /pdf/{numero}</code> - PDF do pedido</li>
            </ul>
        </div>
        
        <div class="info">
            <h3>🔗 Para Power BI:</h3>
            <p>Use estas URLs como fonte de dados:</p>
            <code style="background: #2d5f2d; color: white; padding: 8px; border-radius: 4px; display: block; margin: 5px 0;">
                http://127.0.0.1:5001/clientes
            </code>
            <code style="background: #2d5f2d; color: white; padding: 8px; border-radius: 4px; display: block; margin: 5px 0;">
                http://127.0.0.1:5001/precos
            </code>
            <code style="background: #2d5f2d; color: white; padding: 8px; border-radius: 4px; display: block; margin: 5px 0;">
                http://127.0.0.1:5001/pedidos
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

            # Verificar qual ambiente estamos
            environment = os.getenv('ENVIRONMENT', 'development')
            database_type = "Railway PostgreSQL" if environment == 'production' else "Local PostgreSQL"

            return jsonify({
                'status': 'OK',
                'database': f'{database_type} - Conectado',
                'version': version[:70],
                'environment': environment,
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
        'timestamp': datetime.now().isoformat()
    })


@app.route('/precos')
def listar_precos():
    """Listar preços normais em JSON"""
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
        'tipo': 'normal',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/precos-ld')
def listar_precos_ld():
    """Listar preços LD em JSON"""
    precos = buscar_precos_ld()
    precos_json = []

    for preco in precos:
        precos_json.append({
            'artigo': preco[0],
            'codigo': preco[1],
            'descricao': preco[2],
            'icms_18_ld': float(preco[3]) if preco[3] else 0,
            'icms_12_ld': float(preco[4]) if preco[4] else 0,
            'icms_7_ld': float(preco[5]) if preco[5] else 0,
            'ret_ld_mg': float(preco[6]) if preco[6] else 0
        })

    return jsonify({
        'precos_ld': precos_json,
        'total': len(precos_json),
        'tipo': 'linha_diferenciada',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/criar-pedido', methods=['POST'])
def criar_pedido():
    """Criar novo pedido"""
    try:
        dados = request.get_json()

        # Validar dados básicos
        if not dados or 'cnpj_cliente' not in dados or 'itens' not in dados:
            return jsonify({'erro': 'Dados incompletos'}), 400

        # Obter próximo número
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return jsonify({'erro': 'Erro ao gerar número do pedido'}), 500

        # Calcular valor total
        valor_total = 0
        for item in dados['itens']:
            if 'quantidade' in item and 'preco_unitario' in item:
                item['preco_total'] = item['quantidade'] * \
                    item['preco_unitario']
                valor_total += item['preco_total']

        # Salvar pedido
        sucesso = salvar_pedido(
            numero_pedido=numero_pedido,
            cnpj_cliente=dados['cnpj_cliente'],
            representante=dados.get('representante', ''),
            observacoes=dados.get('observacoes', ''),
            itens=dados['itens'],
            valor_total=valor_total
        )

        if sucesso:
            return jsonify({
                'sucesso': True,
                'numero_pedido': numero_pedido,
                'valor_total': valor_total,
                'message': 'Pedido criado com sucesso'
            })
        else:
            return jsonify({'erro': 'Erro ao salvar pedido'}), 500

    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/pedidos')
def listar_pedidos():
    """Listar todos os pedidos"""
    conn = conectar_postgresql()
    if not conn:
        return jsonify({'erro': 'Erro de conexão'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.numero_pedido, p.cnpj_cliente, c.razao_social, 
                   p.representante, p.valor_total, p.created_at
            FROM pedidos p
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj
            ORDER BY p.created_at DESC
        """)

        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()

        pedidos_json = []
        for pedido in pedidos:
            pedidos_json.append({
                'numero_pedido': pedido[0],
                'cnpj_cliente': pedido[1],
                'razao_social': pedido[2],
                'representante': pedido[3],
                'valor_total': float(pedido[4]) if pedido[4] else 0,
                'created_at': pedido[5].isoformat() if pedido[5] else None
            })

        return jsonify({
            'pedidos': pedidos_json,
            'total': len(pedidos_json),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'erro': str(e)}), 500


@app.route('/pedido/<numero_pedido>')
def buscar_pedido_endpoint(numero_pedido):
    """Buscar pedido específico"""
    pedido = buscar_pedido(numero_pedido)

    if pedido:
        return jsonify(pedido)
    else:
        return jsonify({'erro': 'Pedido não encontrado'}), 404


@app.route('/pdf/<numero_pedido>')
def gerar_pdf_pedido(numero_pedido):
    """Gerar PDF do pedido"""
    pedido = buscar_pedido(numero_pedido)

    if not pedido:
        return jsonify({'erro': 'Pedido não encontrado'}), 404

    try:
        # Criar PDF na memória
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "DESIGNTEX TECIDOS")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, f"Pedido: {pedido['numero_pedido']}")

        # Dados do cliente
        y_pos = height - 110
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y_pos, "CLIENTE:")
        y_pos -= 20
        p.setFont("Helvetica", 10)
        p.drawString(50, y_pos, f"CNPJ: {pedido['cnpj_cliente']}")
        y_pos -= 15
        p.drawString(
            50, y_pos, f"Razao Social: {pedido['razao_social'] or 'N/A'}")
        y_pos -= 15
        if pedido.get('nome_fantasia'):
            p.drawString(
                50, y_pos, f"Nome Fantasia: {pedido['nome_fantasia']}")
            y_pos -= 15

        if pedido.get('representante'):
            p.drawString(
                50, y_pos, f"Representante: {pedido['representante']}")
            y_pos -= 15

        # Itens
        y_pos -= 20
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y_pos, "ITENS:")
        y_pos -= 20

        p.setFont("Helvetica", 9)
        p.drawString(50, y_pos, "Artigo")
        p.drawString(200, y_pos, "Qtd")
        p.drawString(250, y_pos, "Preco Unit")
        p.drawString(320, y_pos, "Total")
        y_pos -= 15

        total_geral = 0
        for item in pedido['itens']:
            if y_pos < 100:  # Nova página se necessário
                p.showPage()
                y_pos = height - 50

            p.drawString(50, y_pos, str(item['artigo'])[:25])
            p.drawString(200, y_pos, str(item['quantidade']))
            p.drawString(250, y_pos, f"R$ {item['preco_unitario']:.2f}")
            p.drawString(320, y_pos, f"R$ {item['preco_total']:.2f}")
            total_geral += item['preco_total']
            y_pos -= 15

        # Total
        y_pos -= 20
        p.setFont("Helvetica-Bold", 12)
        p.drawString(250, y_pos, f"TOTAL GERAL: R$ {total_geral:.2f}")

        # Observações
        if pedido.get('observacoes'):
            y_pos -= 30
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y_pos, "OBSERVACOES:")
            y_pos -= 15
            p.setFont("Helvetica", 9)
            # Quebrar texto em linhas
            obs_lines = pedido['observacoes'].split('\n')
            for line in obs_lines:
                if y_pos < 50:
                    p.showPage()
                    y_pos = height - 50
                p.drawString(50, y_pos, line[:80])
                y_pos -= 12

        # Footer
        p.setFont("Helvetica", 8)
        p.drawString(
            50, 30, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

        p.save()
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'pedido_{numero_pedido}.pdf',
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({'erro': f'Erro ao gerar PDF: {str(e)}'}), 500


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Sistema Completo")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/precos")
        print("💎 Preços LD: http://127.0.0.1:5001/precos-ld")
        print("📋 Pedidos: http://127.0.0.1:5001/pedidos")
        print("-" * 50)

        # Configurar porta do Railway se existir
        port = int(os.getenv('PORT', 5001))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
