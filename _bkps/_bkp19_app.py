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

        # Tabela pedidos (ATUALIZADA com todos os campos)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                nome_representante VARCHAR(100),
                razao_social VARCHAR(200),
                cnpj_cliente VARCHAR(18),
                telefone VARCHAR(20),
                prazo_pagamento VARCHAR(50),
                tipo_pedido VARCHAR(30),
                numero_op VARCHAR(50),
                tipo_frete VARCHAR(30),
                transportadora_fob VARCHAR(100),
                transportadora_cif VARCHAR(100),
                tipo_produto VARCHAR(50),
                venda_triangular VARCHAR(20),
                dados_triangulacao TEXT,
                regime_ret VARCHAR(30),
                tabela_precos VARCHAR(20),
                observacoes TEXT,
                valor_total DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela itens dos pedidos (NOVA)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos_itens (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) NOT NULL,
                artigo VARCHAR(100),
                codigo VARCHAR(50),
                desenho_cor VARCHAR(100),
                metragem DECIMAL(10,2),
                preco_metro DECIMAL(10,2),
                subtotal DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (numero_pedido) REFERENCES pedidos(numero_pedido) ON DELETE CASCADE
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

# NOVAS FUNÇÕES DE PEDIDOS - INSERIR AQUI


def salvar_pedido(dados):
    """Salvar pedido completo no banco PostgreSQL"""

    conn = conectar_postgresql()
    if not conn:
        return {'success': False, 'message': 'Erro na conexão com banco'}

    try:
        cursor = conn.cursor()

        # Obter próximo número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return {'success': False, 'message': 'Erro ao gerar número do pedido'}

        print(f"💾 Salvando pedido {numero_pedido}...")

        # INSERIR PEDIDO PRINCIPAL com TODOS os campos
        cursor.execute("""
            INSERT INTO pedidos (
                numero_pedido, nome_representante, razao_social, cnpj_cliente, telefone,
                prazo_pagamento, tipo_pedido, numero_op, tipo_frete, transportadora_fob,
                transportadora_cif, tipo_produto, venda_triangular, dados_triangulacao,
                regime_ret, tabela_precos, observacoes, valor_total
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            numero_pedido,
            dados.get('nomeRepresentante', ''),
            dados.get('razaoSocial', ''),
            dados.get('cnpj', ''),
            dados.get('telefone', ''),
            dados.get('prazoPagamento', ''),
            dados.get('tipoPedido', ''),
            dados.get('numeroOP', ''),  # NOVO
            dados.get('tipoFrete', ''),
            dados.get('transportadoraFOB', ''),
            dados.get('transportadoraCIF', ''),
            dados.get('tipoProduto', ''),
            dados.get('vendaTriangular', ''),
            dados.get('dadosTriangulacao', ''),
            dados.get('regimeRET', ''),
            dados.get('tabelaPrecos', ''),  # CORRIGIDO
            dados.get('observacoes', ''),
            dados.get('valorTotal', 0)
        ))

        # INSERIR ITENS DO PEDIDO
        produtos = dados.get('produtos', [])
        for produto in produtos:
            cursor.execute("""
                INSERT INTO pedidos_itens (
                    numero_pedido, artigo, codigo, desenho_cor,
                    metragem, preco_metro, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_pedido,
                produto.get('artigo', ''),
                produto.get('codigo', ''),
                produto.get('desenho_cor', ''),
                produto.get('metragem', 0),
                produto.get('preco', 0),
                produto.get('subtotal', 0)
            ))

        conn.commit()
        print(f"✅ Pedido {numero_pedido} salvo com {len(produtos)} itens")

        cursor.close()
        conn.close()

        return {
            'success': True,
            'message': f'Pedido {numero_pedido} salvo com sucesso!',
            'numero_pedido': numero_pedido,
            'valor_total': dados.get('valorTotal', 0)
        }

    except Exception as e:
        print(f"❌ Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'message': f'Erro ao salvar: {str(e)}'}


def buscar_pedido_completo(numero_pedido):
    """Buscar pedido completo com todos os dados"""

    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Buscar dados do pedido principal
        cursor.execute("""
            SELECT 
                numero_pedido, nome_representante, razao_social, cnpj_cliente, telefone,
                prazo_pagamento, tipo_pedido, numero_op, tipo_frete, transportadora_fob,
                transportadora_cif, tipo_produto, venda_triangular, dados_triangulacao,
                regime_ret, tabela_precos, observacoes, valor_total, created_at
            FROM pedidos 
            WHERE numero_pedido = %s
        """, (numero_pedido,))

        pedido = cursor.fetchone()
        if not pedido:
            cursor.close()
            conn.close()
            return None

        # Buscar itens do pedido
        cursor.execute("""
            SELECT artigo, codigo, desenho_cor, metragem, preco_metro, subtotal
            FROM pedidos_itens 
            WHERE numero_pedido = %s
            ORDER BY id
        """, (numero_pedido,))

        itens = cursor.fetchall()

        cursor.close()
        conn.close()

        # Montar estrutura completa
        pedido_completo = {
            'numero_pedido': pedido[0],
            'nome_representante': pedido[1],
            'razao_social': pedido[2],
            'cnpj_cliente': pedido[3],
            'telefone': pedido[4],
            'prazo_pagamento': pedido[5],
            'tipo_pedido': pedido[6],
            'numero_op': pedido[7],
            'tipo_frete': pedido[8],
            'transportadora_fob': pedido[9],
            'transportadora_cif': pedido[10],
            'tipo_produto': pedido[11],
            'venda_triangular': pedido[12],
            'dados_triangulacao': pedido[13],
            'regime_ret': pedido[14],
            'tabela_precos': pedido[15],
            'observacoes': pedido[16],
            'valor_total': float(pedido[17]) if pedido[17] else 0,
            'created_at': pedido[18],
            'itens': []
        }

        # Adicionar itens
        for item in itens:
            pedido_completo['itens'].append({
                'artigo': item[0],
                'codigo': item[1],
                'desenho_cor': item[2],
                'metragem': float(item[3]),
                'preco_metro': float(item[4]),
                'subtotal': float(item[5])
            })

        return pedido_completo

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
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 25px;
            margin: 10px;
            transition: all 0.3s ease;
            font-weight: bold;
        }
        .btn:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        .btn-success {
            background: #28a745;
        }
        .btn-success:hover {
            background: #218838;
        }
        .menu-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
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
        
        <div class="menu-grid">
            <a href="/novo-pedido" class="btn btn-success">📝 NOVO PEDIDO</a>
            <a href="/health" class="btn">🔍 Health Check</a>
            <a href="/clientes" class="btn">👥 Ver Clientes</a>
            <a href="/precos" class="btn">💰 Ver Preços</a>
        </div>
        
        <div class="info">
            <h3>📋 Endpoints Disponíveis:</h3>
            <ul class="endpoints">
                <li><code>GET /</code> - Homepage</li>
                <li><code>GET /novo-pedido</code> - Tela de criar pedido</li>
                <li><code>POST /pedidos</code> - Criar pedido (JSON)</li>
                <li><code>GET /health</code> - Status do sistema</li>
                <li><code>GET /clientes</code> - Lista de clientes</li>
                <li><code>GET /precos</code> - Tabela de preços</li>
                <li><code>GET /gerar-pdf/{numero}</code> - PDF do pedido</li>
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
                'database': 'PostgreSQL - Conectado',
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
        'total': len(clientes_json)
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
        'total': len(precos_json)
    })

# NOVOS ENDPOINTS PARA PEDIDOS


@app.route('/pedidos', methods=['POST'])
def criar_pedido():
    """Criar novo pedido"""
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({'success': False, 'message': 'Dados não fornecidos'}), 400

        resultado = salvar_pedido(dados)

        if resultado['success']:
            return jsonify(resultado), 201
        else:
            return jsonify(resultado), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        }), 500


@app.route('/pedidos/<numero_pedido>')
def buscar_pedido(numero_pedido):
    """Buscar pedido por número"""
    try:
        pedido = buscar_pedido_completo(numero_pedido)

        if pedido:
            return jsonify({'success': True, 'pedido': pedido})
        else:
            return jsonify({'success': False, 'message': 'Pedido não encontrado'}), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar pedido: {str(e)}'
        }), 500


@app.route('/novo-pedido')
def novo_pedido():
    """Tela para criar novo pedido"""
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
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #667eea;
        }
        .header h1 {
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        .form-group {
            display: flex;
            flex-direction: column;
        }
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        label {
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }
        input, select, textarea {
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .items-section {
            background: #f8f9ff;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .item-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto;
            gap: 15px;
            align-items: end;
            margin-bottom: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        .btn-success {
            background: #28a745;
            color: white;
        }
        .btn-success:hover {
            background: #218838;
        }
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .btn-add {
            background: #17a2b8;
            color: white;
            margin-bottom: 15px;
        }
        .total-section {
            background: #e8f5e8;
            padding: 20px;
            border-radius: 10px;
            text-align: right;
        }
        .total-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #2d5f2d;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
            color: #667eea;
            text-decoration: none;
            font-weight: bold;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .success-message {
            display: none;
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border: 1px solid #c3e6cb;
        }
        .error-message {
            display: none;
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border: 1px solid #f5c6cb;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Voltar ao Menu Principal</a>
        
        <div class="header">
            <h1>🏭 NOVO PEDIDO DE VENDAS</h1>
            <p>DESIGNTEX TECIDOS - Sistema DTX</p>
        </div>

        <div class="success-message" id="successMessage"></div>
        <div class="error-message" id="errorMessage"></div>

        <form id="pedidoForm">
            <div class="form-grid">
                <div class="form-group">
                    <label for="numeroPedido">Número do Pedido:</label>
                    <input type="text" id="numeroPedido" name="numeroPedido" readonly style="background: #f0f0f0;">
                </div>
                
                <div class="form-group">
                    <label for="representante">Representante:</label>
                    <input type="text" id="representante" name="representante" required placeholder="Nome do representante">
                </div>
                
                <div class="form-group">
                    <label for="clienteCnpj">Cliente:</label>
                    <select id="clienteCnpj" name="clienteCnpj" required>
                        <option value="">Selecione um cliente...</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="dataEntrega">Data de Entrega:</label>
                    <input type="date" id="dataEntrega" name="dataEntrega">
                </div>
                
                <div class="form-group full-width">
                    <label for="observacoes">Observações:</label>
                    <textarea id="observacoes" name="observacoes" rows="3" placeholder="Observações gerais do pedido..."></textarea>
                </div>
            </div>

            <div class="items-section">
                <h3 style="color: #667eea; margin-bottom: 20px;">📦 ITENS DO PEDIDO</h3>
                
                <button type="button" class="btn btn-add" onclick="adicionarItem()">+ Adicionar Item</button>
                
                <div id="itensContainer">
                    <div class="item-row" data-item="0">
                        <div>
                            <label>Produto:</label>
                            <select name="produtos[]" required onchange="atualizarPreco(0)">
                                <option value="">Selecione um produto...</option>
                            </select>
                        </div>
                        <div>
                            <label>Quantidade:</label>
                            <input type="number" name="quantidades[]" min="1" step="1" required onchange="calcularTotal()">
                        </div>
                        <div>
                            <label>Preço Unit.:</label>
                            <input type="number" name="precos[]" step="0.01" min="0" required onchange="calcularTotal()">
                        </div>
                        <div>
                            <label>ICMS:</label>
                            <select name="icms[]" onchange="atualizarPrecoIcms(0)">
                                <option value="18">18%</option>
                                <option value="12">12%</option>
                                <option value="7">7%</option>
                                <option value="ret">Ret. MG</option>
                            </select>
                        </div>
                        <div>
                            <label>Subtotal:</label>
                            <input type="text" name="subtotais[]" readonly style="background: #f0f0f0;">
                        </div>
                        <div>
                            <label>&nbsp;</label>
                            <button type="button" class="btn btn-danger" onclick="removerItem(0)">🗑️</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="total-section">
                <div class="total-value">
                    Total do Pedido: R$ <span id="totalPedido">0,00</span>
                </div>
            </div>

            <div style="text-align: center; margin-top: 30px;">
                <button type="submit" class="btn btn-success" style="padding: 15px 40px; font-size: 18px;">
                    💾 SALVAR PEDIDO
                </button>
            </div>
        </form>

        <div class="loading" id="loading">
            <p>⏳ Salvando pedido...</p>
        </div>
    </div>

    <script>
        let itemCount = 1;
        let clientes = [];
        let produtos = [];

        // Carregar dados iniciais
        document.addEventListener('DOMContentLoaded', function() {
            carregarNumeroPedido();
            carregarClientes();
            carregarProdutos();
        });

        async function carregarNumeroPedido() {
            try {
                const response = await fetch('/api/proximo-numero-pedido');
                const data = await response.json();
                document.getElementById('numeroPedido').value = data.numero;
            } catch (error) {
                console.error('Erro ao carregar número do pedido:', error);
            }
        }

        async function carregarClientes() {
            try {
                const response = await fetch('/clientes');
                const data = await response.json();
                clientes = data.clientes;
                
                const select = document.getElementById('clienteCnpj');
                clientes.forEach(cliente => {
                    const option = document.createElement('option');
                    option.value = cliente.cnpj;
                    option.textContent = `${cliente.cnpj} - ${cliente.razao_social}`;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Erro ao carregar clientes:', error);
            }
        }

        async function carregarProdutos() {
            try {
                const response = await fetch('/precos');
                const data = await response.json();
                produtos = data.precos;
                
                atualizarSelectsProdutos();
            } catch (error) {
                console.error('Erro ao carregar produtos:', error);
            }
        }

        function atualizarSelectsProdutos() {
            const selects = document.querySelectorAll('select[name="produtos[]"]');
            selects.forEach(select => {
                // Limpar opções existentes (exceto a primeira)
                while (select.children.length > 1) {
                    select.removeChild(select.lastChild);
                }
                
                produtos.forEach(produto => {
                    const option = document.createElement('option');
                    option.value = JSON.stringify(produto);
                    option.textContent = `${produto.artigo} - ${produto.descricao}`;
                    select.appendChild(option);
                });
            });
        }

        function adicionarItem() {
            const container = document.getElementById('itensContainer');
            const novoItem = document.createElement('div');
            novoItem.className = 'item-row';
            novoItem.setAttribute('data-item', itemCount);
            
            novoItem.innerHTML = `
                <div>
                    <label>Produto:</label>
                    <select name="produtos[]" required onchange="atualizarPreco(${itemCount})">
                        <option value="">Selecione um produto...</option>
                    </select>
                </div>
                <div>
                    <label>Quantidade:</label>
                    <input type="number" name="quantidades[]" min="1" step="1" required onchange="calcularTotal()">
                </div>
                <div>
                    <label>Preço Unit.:</label>
                    <input type="number" name="precos[]" step="0.01" min="0" required onchange="calcularTotal()">
                </div>
                <div>
                    <label>ICMS:</label>
                    <select name="icms[]" onchange="atualizarPrecoIcms(${itemCount})">
                        <option value="18">18%</option>
                        <option value="12">12%</option>
                        <option value="7">7%</option>
                        <option value="ret">Ret. MG</option>
                    </select>
                </div>
                <div>
                    <label>Subtotal:</label>
                    <input type="text" name="subtotais[]" readonly style="background: #f0f0f0;">
                </div>
                <div>
                    <label>&nbsp;</label>
                    <button type="button" class="btn btn-danger" onclick="removerItem(${itemCount})">🗑️</button>
                </div>
            `;
            
            container.appendChild(novoItem);
            itemCount++;
            
            // Atualizar selects de produtos no novo item
            atualizarSelectsProdutos();
        }

        function removerItem(itemId) {
            const item = document.querySelector(`[data-item="${itemId}"]`);
            if (item && document.querySelectorAll('.item-row').length > 1) {
                item.remove();
                calcularTotal();
            }
        }

        function atualizarPreco(itemId) {
            const item = document.querySelector(`[data-item="${itemId}"]`);
            const selectProduto = item.querySelector('select[name="produtos[]"]');
            const inputPreco = item.querySelector('input[name="precos[]"]');
            
            if (selectProduto.value) {
                const produto = JSON.parse(selectProduto.value);
                inputPreco.value = produto.icms_18.toFixed(2);
                atualizarPrecoIcms(itemId);
            }
        }

        function atualizarPrecoIcms(itemId) {
            const item = document.querySelector(`[data-item="${itemId}"]`);
            const selectProduto = item.querySelector('select[name="produtos[]"]');
            const selectIcms = item.querySelector('select[name="icms[]"]');
            const inputPreco = item.querySelector('input[name="precos[]"]');
            
            if (selectProduto.value) {
                const produto = JSON.parse(selectProduto.value);
                const icms = selectIcms.value;
                
                let preco = 0;
                switch (icms) {
                    case '18': preco = produto.icms_18; break;
                    case '12': preco = produto.icms_12; break;
                    case '7': preco = produto.icms_7; break;
                    case 'ret': preco = produto.ret_mg; break;
                }
                
                inputPreco.value = preco.toFixed(2);
                calcularTotal();
            }
        }

        function calcularTotal() {
            const items = document.querySelectorAll('.item-row');
            let total = 0;
            
            items.forEach(item => {
                const quantidade = parseFloat(item.querySelector('input[name="quantidades[]"]').value) || 0;
                const preco = parseFloat(item.querySelector('input[name="precos[]"]').value) || 0;
                const subtotal = quantidade * preco;
                
                item.querySelector('input[name="subtotais[]"]').value = subtotal.toFixed(2);
                total += subtotal;
            });
            
            document.getElementById('totalPedido').textContent = total.toLocaleString('pt-BR', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        // Submeter formulário
        document.getElementById('pedidoForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const loading = document.getElementById('loading');
            const successMessage = document.getElementById('successMessage');
            const errorMessage = document.getElementById('errorMessage');
            
            // Limpar mensagens
            successMessage.style.display = 'none';
            errorMessage.style.display = 'none';
            loading.style.display = 'block';
            
            try {
                const formData = new FormData(this);
                const pedidoData = {
                    numero_pedido: formData.get('numeroPedido'),
                    cnpj_cliente: formData.get('clienteCnpj'),
                    representante: formData.get('representante'),
                    observacoes: formData.get('observacoes'),
                    itens: []
                };
                
                const produtos = formData.getAll('produtos[]');
                const quantidades = formData.getAll('quantidades[]');
                const precos = formData.getAll('precos[]');
                
                for (let i = 0; i < produtos.length; i++) {
                    if (produtos[i]) {
                        const produto = JSON.parse(produtos[i]);
                        pedidoData.itens.push({
                            produto: produto.artigo,
                            quantidade: parseInt(quantidades[i]),
                            preco_unitario: parseFloat(precos[i]),
                            subtotal: parseInt(quantidades[i]) * parseFloat(precos[i])
                        });
                    }
                }
                
                const response = await fetch('/pedidos', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(pedidoData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    successMessage.innerHTML = `
                        ✅ Pedido ${result.numero_pedido} criado com sucesso!<br>
                        <a href="/gerar-pdf/${result.numero_pedido}" target="_blank">📄 Ver PDF</a>
                    `;
                    successMessage.style.display = 'block';
                    this.reset();
                    carregarNumeroPedido();
                } else {
                    throw new Error(result.error || 'Erro ao criar pedido');
                }
                
            } catch (error) {
                errorMessage.textContent = `❌ Erro: ${error.message}`;
                errorMessage.style.display = 'block';
            } finally {
                loading.style.display = 'none';
            }
        });
    </script>
</body>
</html>
    ''')


@app.route('/api/proximo-numero-pedido')
def api_proximo_numero_pedido():
    """API para obter próximo número de pedido"""
    numero = obter_proximo_numero_pedido()
    if numero:
        return jsonify({'numero': numero})
    else:
        return jsonify({'error': 'Erro ao obter número do pedido'}), 500


@app.route('/gerar-pdf/<numero_pedido>')
def gerar_pdf_pedido(numero_pedido):
    """Gerar PDF do pedido"""
    try:
        conn = conectar_postgresql()
        if not conn:
            return "Erro de conexão com banco", 500

        cursor = conn.cursor()

        # Buscar dados do pedido
        cursor.execute("""
            SELECT p.numero_pedido, p.cnpj_cliente, p.representante, 
                   p.observacoes, p.valor_total, p.created_at,
                   c.razao_social, c.nome_fantasia
            FROM pedidos p
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj
            WHERE p.numero_pedido = %s
        """, (numero_pedido,))

        pedido = cursor.fetchone()

        if not pedido:
            cursor.close()
            conn.close()
            return "Pedido não encontrado", 404

        cursor.close()
        conn.close()

        # Gerar PDF simples
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)

        # Cabeçalho
        p.setFont("Helvetica-Bold", 20)
        p.drawString(50, 800, "DESIGNTEX TECIDOS")
        p.setFont("Helvetica", 12)
        p.drawString(50, 780, "PEDIDO DE VENDAS")

        # Dados do pedido
        y = 750
        p.drawString(50, y, f"Pedido: {pedido[0]}")
        y -= 20
        p.drawString(50, y, f"Cliente: {pedido[6]} ({pedido[1]})")
        y -= 20
        p.drawString(50, y, f"Representante: {pedido[2]}")
        y -= 20
        p.drawString(50, y, f"Data: {pedido[5].strftime('%d/%m/%Y %H:%M')}")
        y -= 20
        p.drawString(50, y, f"Valor Total: R$ {float(pedido[4]):,.2f}")

        if pedido[3]:  # observações
            y -= 30
            p.drawString(50, y, "Observações:")
            y -= 15
            p.drawString(50, y, str(pedido[3])[:100])

        p.showPage()
        p.save()

        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f'pedido_{numero_pedido}.pdf', mimetype='application/pdf')

    except Exception as e:
        return f"Erro ao gerar PDF: {str(e)}", 500


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - PostgreSQL Web")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/preços")
        print("📋 Criar pedido: POST http://127.0.0.1:5001/pedidos")
        print("-" * 50)

        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
