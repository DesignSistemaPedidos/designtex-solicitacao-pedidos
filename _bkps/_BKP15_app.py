import os
import sys
import locale
import psycopg2
from flask import Flask, render_template_string, request, jsonify, send_file, render_template
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

            if 'database_url' in DATABASE_CONFIG:
                database_url = DATABASE_CONFIG['database_url']

                if '?' in database_url:
                    database_url += f'&client_encoding={encoding}'
                else:
                    database_url += f'?client_encoding={encoding}'

                conn = psycopg2.connect(database_url)

            else:
                config = DATABASE_CONFIG.copy()
                config['client_encoding'] = encoding
                conn = psycopg2.connect(**config)

            conn.set_client_encoding(encoding)

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

        try:
            cursor.execute("SET client_encoding TO 'SQL_ASCII';")
            cursor.execute("SET standard_conforming_strings TO on;")
            print("✅ Encoding da sessão configurado")
        except:
            print("⚠️  Usando encoding padrão do servidor")

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

        # Tabela pedidos - ATUALIZADA com novos campos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                razao_social_cliente VARCHAR(200),
                representante VARCHAR(100),
                telefone VARCHAR(20),
                prazo_pagamento VARCHAR(50),
                tipo_pedido VARCHAR(10),
                numero_op VARCHAR(50),
                tipo_frete VARCHAR(10),
                transportadora_fob TEXT,
                transportadora_cif TEXT,
                venda_triangular VARCHAR(10),
                dados_triangulacao TEXT,
                regime_ret VARCHAR(10),
                tipo_produto VARCHAR(20),
                tabela_precos VARCHAR(50),
                observacoes TEXT,
                valor_total DECIMAL(10,2),
                status VARCHAR(20) DEFAULT 'ATIVO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela itens_pedido - NOVA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10),
                artigo VARCHAR(100),
                codigo VARCHAR(50),
                desenho_cor VARCHAR(100),
                metragem DECIMAL(10,2),
                preco_metro DECIMAL(10,2),
                subtotal DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (numero_pedido) REFERENCES pedidos(numero_pedido)
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

        clientes = [
            ('12.345.678/0001-90', 'EMPRESA ABC LTDA', 'EMPRESA ABC', '11999990001'),
            ('98.765.432/0001-10', 'COMERCIAL XYZ SA',
             'COMERCIAL XYZ', '11999990002'),
            ('11.222.333/0001-44', 'DISTRIBUIDORA 123 LTDA',
             'DISTRIBUIDORA 123', '11999990003'),
            ('22.333.444/0001-55', 'CONFECCOES MODELO LTDA',
             'CONFECCOES MODELO', '11999990004'),
            ('33.444.555/0001-66', 'TEXTIL NACIONAL SA',
             'TEXTIL NACIONAL', '11999990005')
        ]

        for cnpj, razao, fantasia, telefone in clientes:
            cursor.execute("""
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (cnpj) DO NOTHING
            """, (cnpj, razao, fantasia, telefone))

        conn.commit()
        print("✅ Clientes iniciais inseridos!")

        print("📋 Inserindo preços iniciais...")

        precos = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 30/1', 'VIS301', 'Tecido viscose 30/1 lisa',
             18.20, 17.40, 16.80, 16.30),
            ('MALHA COTTON', 'MAL001', 'Malha cotton penteada',
             22.80, 21.90, 21.20, 20.70),
            ('LYCRA COTTON', 'LYC001', 'Lycra cotton elastano',
             28.50, 27.30, 26.50, 25.90)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        # Preços LD (Lista Diferenciada)
        precos_ld = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado LD',
             11.20, 10.50, 9.90, 9.60),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D LD',
             13.80, 13.10, 12.40, 12.00),
            ('VISCOSE 30/1', 'VIS301', 'Tecido viscose 30/1 lisa LD',
             16.40, 15.60, 15.00, 14.70),
            ('MALHA COTTON', 'MAL001', 'Malha cotton penteada LD',
             20.50, 19.70, 19.00, 18.60),
            ('LYCRA COTTON', 'LYC001', 'Lycra cotton elastano LD',
             25.60, 24.60, 23.80, 23.30)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos_ld:
            cursor.execute("""
                INSERT INTO precos_ld (artigo, codigo, descricao, icms_18_ld, icms_12_ld, icms_7_ld, ret_ld_mg) 
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
        return str(numero).zfill(4)
    except Exception as e:
        print(f"Erro ao obter número do pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None


def buscar_clientes_por_texto(query):
    """Buscar clientes por texto (autocomplete)"""
    conn = conectar_postgresql()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cnpj, razao_social, nome_fantasia, telefone 
            FROM clientes 
            WHERE UPPER(razao_social) LIKE UPPER(%s) 
               OR UPPER(nome_fantasia) LIKE UPPER(%s)
               OR cnpj LIKE %s
            ORDER BY razao_social
            LIMIT 10
        """, (f'%{query}%', f'%{query}%', f'%{query}%'))

        clientes = cursor.fetchall()
        cursor.close()
        conn.close()

        return [
            {
                'cnpj': cliente[0],
                'razao_social': cliente[1],
                'nome_fantasia': cliente[2],
                'telefone': cliente[3] or ''
            }
            for cliente in clientes
        ]
    except Exception as e:
        print(f"Erro ao buscar clientes: {e}")
        if conn:
            conn.close()
        return []


def salvar_pedido(dados):
    """Salvar pedido completo no banco"""
    conn = conectar_postgresql()
    if not conn:
        return {'success': False, 'message': 'Erro de conexão com banco'}

    try:
        cursor = conn.cursor()

        # Obter número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return {'success': False, 'message': 'Erro ao gerar número do pedido'}

        # Inserir pedido principal
        cursor.execute("""
            INSERT INTO pedidos (
                numero_pedido, cnpj_cliente, razao_social_cliente, representante,
                telefone, prazo_pagamento, tipo_pedido, numero_op, tipo_frete,
                transportadora_fob, transportadora_cif, venda_triangular,
                dados_triangulacao, regime_ret, tipo_produto, tabela_precos,
                observacoes, valor_total
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero_pedido,
            dados.get('cnpj', ''),
            dados.get('razaoSocial', ''),
            dados.get('nomeRepresentante', ''),
            dados.get('telefone', ''),
            dados.get('prazoPagamento', ''),
            dados.get('tipoPedido', ''),
            dados.get('numeroOP', ''),
            dados.get('tipoFrete', ''),
            dados.get('transportadoraFOB', ''),
            dados.get('transportadoraCIF', ''),
            dados.get('vendaTriangular', ''),
            dados.get('dadosTriangulacao', ''),
            dados.get('regimeRET', ''),
            dados.get('tipoProduto', ''),
            dados.get('tabelaPrecos', ''),
            dados.get('observacoes', ''),
            float(dados.get('valorTotal', 0))
        ))

        # Inserir itens do pedido
        for produto in dados.get('produtos', []):
            cursor.execute("""
                INSERT INTO itens_pedido (
                    numero_pedido, artigo, codigo, desenho_cor,
                    metragem, preco_metro, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_pedido,
                produto.get('artigo', ''),
                produto.get('codigo', ''),
                produto.get('desenho_cor', ''),
                float(produto.get('metragem', 0)),
                float(produto.get('preco', 0)),
                float(produto.get('subtotal', 0))
            ))

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Pedido {numero_pedido} salvo com sucesso!")

        return {
            'success': True,
            'message': f'Pedido {numero_pedido} salvo com sucesso!',
            'numero_pedido': numero_pedido,
            'valor_total': f"R$ {float(dados.get('valorTotal', 0)):.2f}".replace('.', ',')
        }

    except Exception as e:
        print(f"❌ Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'message': f'Erro ao salvar no banco: {str(e)}'}


# FLASK APP
app = Flask(__name__)


@app.route('/')
def form_pedido():
    """Página do formulário de pedidos"""

    # Prazos de pagamento disponíveis
    prazos = [
        'À vista',
        '30 dias',
        '60 dias',
        '90 dias',
        '30/60 dias',
        '30/60/90 dias',
        'Outros'
    ]

    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pedido de Vendas - Designtex Tecidos</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- CSS customizado -->
    <style>
        body {
            background-color: #80858b;
            font-family: 'Arial', sans-serif;
        }

        .container {
            background-color: white;
            border-radius: 15px;
            padding: 30px;
            margin: 20px auto;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            max-width: 1000px;
        }

        .header-title {
            color: #1a5490;
            text-align: center;
            font-weight: bold;
            margin-bottom: 30px;
            font-size: 28px;
        }

        /* Autocomplete customizado */
        .autocomplete-container {
            position: relative;
        }

        .autocomplete-dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-top: none;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            display: none;
        }

        .autocomplete-item {
            padding: 12px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            font-size: 14px;
        }

        .autocomplete-item:hover {
            background-color: #f5f5f5;
        }

        .autocomplete-item:last-child {
            border-bottom: none;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                padding: 20px;
            }

            .header-title {
                font-size: 22px;
            }
        }

        .btn-primary {
            background-color: #1a5490;
            border-color: #1a5490;
        }

        .btn-primary:hover {
            background-color: #134072;
            border-color: #134072;
        }
    </style>
</head>

<body>
    <div class="container">
        <h1 class="header-title">PEDIDO DE VENDAS<br>DESIGNTEX TECIDOS</h1>

        <form id="pedidoForm">
            <!-- PARTE 1 - CABEÇALHO -->
            <div class="card mb-4">
                <div class="card-header" style="background-color: #1a5490; color: white;">
                    <h5 class="mb-0">📋 DADOS DO CABEÇALHO</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="nomeRepresentante" class="form-label">Nome do Representante *</label>
                            <input type="text" class="form-control" id="nomeRepresentante" required>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="razaoSocial" class="form-label">Razão Social do Cliente *</label>
                            <div class="autocomplete-container">
                                <input type="text" class="form-control" id="razaoSocial"
                                    placeholder="Digite para buscar..." required>
                                <div id="autocomplete-dropdown" class="autocomplete-dropdown"></div>
                            </div>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="cnpj" class="form-label">CNPJ do Cliente *</label>
                            <input type="text" class="form-control" id="cnpj" readonly
                                style="background-color: #f8f9fa;">
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="telefone" class="form-label">Telefone de Contato *</label>
                            <input type="text" class="form-control" id="telefone" required>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PARTE 2 - CORPO DO PEDIDO -->
            <div class="card mb-4">
                <div class="card-header" style="background-color: #1a5490; color: white;">
                    <h5 class="mb-0">⚙️ CONDIÇÕES DO PEDIDO</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="prazoPagamento" class="form-label">Prazo de Pagamento *</label>
                            <select class="form-select" id="prazoPagamento" required>
                                <option value="">Selecione...</option>
                                {% for prazo in prazos %}
                                <option value="{{ prazo }}">{{ prazo }}</option>
                                {% endfor %}
                            </select>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="tipoPedido" class="form-label">Tipo de Pedido *</label>
                            <select class="form-select" id="tipoPedido" required>
                                <option value="">Selecione...</option>
                                <option value="OP">OP (Programação de pedidos)</option>
                                <option value="PE">PE (Pronta-entrega)</option>
                            </select>
                        </div>

                        <div id="campoNumeroOP" class="col-md-6 mb-3" style="display:none;">
                            <label for="numeroOP" class="form-label">Número da OP *</label>
                            <input type="text" class="form-control" id="numeroOP" placeholder="Digite o número da OP">
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="tipoFrete" class="form-label">Tipo de Frete *</label>
                            <select class="form-select" id="tipoFrete" required>
                                <option value="">Selecione...</option>
                                <option value="CIF">CIF</option>
                                <option value="FOB">FOB</option>
                            </select>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="tipoProduto" class="form-label">Tipo de Produto *</label>
                            <select class="form-select" id="tipoProduto" required>
                                <option value="">Selecione...</option>
                                <option value="Liso">Liso</option>
                                <option value="Estampado">Estampado</option>
                                <option value="Digital">Digital</option>
                            </select>
                        </div>
                    </div>

                    <!-- Campos condicionais de frete -->
                    <div id="campoTransportadoraFOB" class="mb-3" style="display:none;">
                        <label for="transportadoraFOB" class="form-label">Transportadora FOB</label>
                        <input type="text" class="form-control" id="transportadoraFOB"
                            placeholder="Digite os dados da transportadora FOB">
                    </div>

                    <div id="campoTransportadoraCIF" class="mb-3" style="display:none;">
                        <label for="transportadoraCIF" class="form-label">Transportadora CIF</label>
                        <input type="text" class="form-control" id="transportadoraCIF"
                            placeholder="Digite os dados da transportadora CIF">
                    </div>

                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="vendaTriangular" class="form-label">Venda Triangular *</label>
                            <select class="form-select" id="vendaTriangular" required>
                                <option value="Não">Não</option>
                                <option value="Sim">Sim</option>
                            </select>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="regimeRET" class="form-label">Regime Fiscal R.E.T * (Somente MG) </label>
                            <select class="form-select" id="regimeRET" required>
                                <option value="Não">Não</option>
                                <option value="Sim">Sim</option>
                            </select>
                        </div>
                    </div>

                    <div id="campoTriangulacao" class="mb-3" style="display:none;">
                        <label for="dadosTriangulacao" class="form-label">Dados da Triangulação</label>
                        <textarea class="form-control" id="dadosTriangulacao" rows="2"
                            placeholder="Digite os dados da triangulação"></textarea>
                    </div>
                </div>
            </div>

            <!-- PARTE 3 - TABELA DE PREÇOS -->
            <div class="card mb-4">
                <div class="card-header" style="background-color: #1a5490; color: white;">
                    <h5 class="mb-0">💰 TABELA DE PREÇOS</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">Selecione a Tabela de Preços *</label>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="border p-3 rounded">
                                    <h6>ICMS Normal</h6>
                                    <div>
                                        <input type="radio" id="icms18_normal" name="tabelaPrecos" value="ICMS 18%" required>
                                        <label for="icms18_normal" class="form-check-label me-3">ICMS 18%</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms12_normal" name="tabelaPrecos" value="ICMS 12%" required>
                                        <label for="icms12_normal" class="form-check-label me-3">ICMS 12%</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms7_normal" name="tabelaPrecos" value="ICMS 7%" required>
                                        <label for="icms7_normal" class="form-check-label me-3">ICMS 7%</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="ret_normal" name="tabelaPrecos" value="RET (SOMENTE MG)" required>
                                        <label for="ret_normal" class="form-check-label">RET (SOMENTE MG)</label>
                                    </div>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="border p-3 rounded">
                                    <h6>ICMS LD</h6>
                                    <div>
                                        <input type="radio" id="icms18_ld" name="tabelaPrecos" value="ICMS 18% LD" required>
                                        <label for="icms18_ld" class="form-check-label me-3">ICMS 18% LD</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms12_ld" name="tabelaPrecos" value="ICMS 12% LD" required>
                                        <label for="icms12_ld" class="form-check-label me-3">ICMS 12% LD</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms7_ld" name="tabelaPrecos" value="ICMS 7% LD" required>
                                        <label for="icms7_ld" class="form-check-label me-3">ICMS 7% LD</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="ret_ld" name="tabelaPrecos" value="RET LD (SOMENTE MG)" required>
                                        <label for="ret_ld" class="form-check-label">RET LD (SOMENTE MG)</label>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="mt-2">
                            <small class="text-muted">⚠️ Selecione apenas uma opção: ICMS Normal OU ICMS LD</small>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PARTE 4 - PRODUTOS -->
            <div class="card mb-4">
                <div class="card-header" style="background-color: #1a5490; color: white;">
                    <h5 class="mb-0">📦 PRODUTOS</h5>
                </div>
                <div class="card-body">
                    <div id="produtos-container">
                        <!-- Produtos serão adicionados aqui via JavaScript -->
                    </div>

                    <button type="button" class="btn btn-secondary mb-3" onclick="adicionarProduto()">
                        ➕ Adicionar Produto
                    </button>

                    <div class="text-end">
                        <h4>Total: R$ <span id="valorTotal">0,00</span></h4>
                    </div>
                </div>
            </div>

            <!-- PARTE 5 - OBSERVAÇÕES -->
            <div class="card mb-4">
                <div class="card-header" style="background-color: #1a5490; color: white;">
                    <h5 class="mb-0">📝 OBSERVAÇÕES</h5>
                </div>
                <div class="card-body">
                    <textarea class="form-control" id="observacoes" rows="4" maxlength="500"
                        placeholder="Observações adicionais (máximo 500 caracteres)"></textarea>
                    <div class="form-text">
                        <span id="contadorCaracteres">0</span>/500 caracteres
                    </div>
                </div>
            </div>

            <!-- BOTÕES -->
            <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                <button type="submit" class="btn btn-primary btn-lg me-md-2">
                    📤 Enviar Pedido
                </button>
                <button type="button" class="btn btn-secondary btn-lg" onclick="limparFormulario()">
                    🗑️ Cancelar
                </button>
            </div>
        </form>
    </div>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        let contadorProdutos = 0;
        let timeoutId;

        // ========== AUTOCOMPLETE DE CLIENTES ==========
        document.getElementById('razaoSocial').addEventListener('input', function (e) {
            const query = e.target.value.trim();
            const dropdown = document.getElementById('autocomplete-dropdown');

            clearTimeout(timeoutId);

            if (query.length < 1) {
                dropdown.style.display = 'none';
                limparDadosCliente();
                return;
            }

            timeoutId = setTimeout(() => {
                buscarClientes(query);
            }, 300);
        });

        function buscarClientes(query) {
            fetch(`/api/buscar_clientes?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    mostrarResultados(data);
                })
                .catch(error => {
                    console.error('Erro na busca:', error);
                });
        }

        function mostrarResultados(clientes) {
            const dropdown = document.getElementById('autocomplete-dropdown');
            dropdown.innerHTML = '';

            if (clientes.length === 0) {
                dropdown.style.display = 'none';
                return;
            }

            clientes.forEach(cliente => {
                const item = document.createElement('div');
                item.className = 'autocomplete-item';
                item.innerHTML = `
                    <strong>${cliente.razao_social}</strong><br>
                    <small style="color: #666;">CNPJ: ${cliente.cnpj}</small>
                `;

                item.addEventListener('click', () => {
                    selecionarCliente(cliente);
                });

                dropdown.appendChild(item);
            });

            dropdown.style.display = 'block';
        }

        function selecionarCliente(cliente) {
            document.getElementById('razaoSocial').value = cliente.razao_social;
            document.getElementById('cnpj').value = cliente.cnpj;
            document.getElementById('telefone').value = cliente.telefone || '';
            document.getElementById('autocomplete-dropdown').style.display = 'none';
        }

        function limparDadosCliente() {
            document.getElementById('cnpj').value = '';
            document.getElementById('telefone').value = '';
        }

        // Fechar dropdown ao clicar fora
        document.addEventListener('click', function (e) {
            if (!e.target.closest('.autocomplete-container')) {
                document.getElementById('autocomplete-dropdown').style.display = 'none';
            }
        });

        // ========== CAMPOS CONDICIONAIS ==========
        document.getElementById('tipoPedido').addEventListener('change', function () {
            const tipoPedido = this.value;
            const campoNumeroOP = document.getElementById('campoNumeroOP');
            const inputNumeroOP = document.getElementById('numeroOP');

            if (tipoPedido === 'OP') {
                campoNumeroOP.style.display = 'block';
                inputNumeroOP.required = true;
            } else {
                campoNumeroOP.style.display = 'none';
                inputNumeroOP.required = false;
                inputNumeroOP.value = '';
            }
        });

        document.getElementById('tipoFrete').addEventListener('change', function () {
            const frete = this.value;
            const campoFOB = document.getElementById('campoTransportadoraFOB');
            const campoCIF = document.getElementById('campoTransportadoraCIF');

            if (frete === 'FOB') {
                campoFOB.style.display = 'block';
                campoCIF.style.display = 'none';
            } else if (frete === 'CIF') {
                campoCIF.style.display = 'block';
                campoFOB.style.display = 'none';
            } else {
                campoFOB.style.display = 'none';
                campoCIF.style.display = 'none';
            }
        });

        document.getElementById('vendaTriangular').addEventListener('change', function () {
            const triangular = this.value;
            const campo = document.getElementById('campoTriangulacao');

            if (triangular === 'Sim') {
                campo.style.display = 'block';
                document.getElementById('dadosTriangulacao').required = true;
            } else {
                campo.style.display = 'none';
                document.getElementById('dadosTriangulacao').required = false;
            }
        });

        // ========== PRODUTOS ==========
        function adicionarProduto() {
            contadorProdutos++;
            const container = document.getElementById('produtos-container');

            const produtoDiv = document.createElement('div');
            produtoDiv.className = 'produto-item mb-4 p-3 border rounded';
            produtoDiv.id = `produto-${contadorProdutos}`;

            produtoDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">Produto ${contadorProdutos}</h6>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="removerProduto(${contadorProdutos})">❌ Remover</button>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-2">
                        <label class="form-label">Artigo *</label>
                        <input type="text" class="form-control" name="artigo" required>
                    </div>
                    <div class="col-md-6 mb-2">
                        <label class="form-label">Código do Artigo *</label>
                        <input type="text" class="form-control" name="codigo" required>
                    </div>
                    <div class="col-md-6 mb-2">
                        <label class="form-label">Desenho/Cor *</label>
                        <input type="text" class="form-control" name="desenho_cor" required>
                    </div>
                    <div class="col-md-2 mb-2">
                        <label class="form-label">Metragem *</label>
                        <input type="number" class="form-control" name="metragem" step="0.01" 
                               required onchange="calcularSubtotal(${contadorProdutos})">
                    </div>
                    <div class="col-md-2 mb-2">
                        <label class="form-label">Preço/Metro *</label>
                        <input type="number" class="form-control" name="preco" step="0.01" 
                               required onchange="calcularSubtotal(${contadorProdutos})">
                    </div>
                    <div class="col-md-2 mb-2">
                        <label class="form-label">Subtotal</label>
                        <input type="text" class="form-control subtotal" readonly 
                               style="background-color: #f8f9fa;" value="R$ 0,00">
                    </div>
                </div>
            `;

            container.appendChild(produtoDiv);
        }

        function removerProduto(id) {
            const produto = document.getElementById(`produto-${id}`);
            if (produto) {
                produto.remove();
                calcularTotal();
            }
        }

        function calcularSubtotal(id) {
            const produto = document.getElementById(`produto-${id}`);
            const metragem = parseFloat(produto.querySelector('input[name="metragem"]').value) || 0;
            const preco = parseFloat(produto.querySelector('input[name="preco"]').value) || 0;
            const subtotal = metragem * preco;

            produto.querySelector('.subtotal').value = `R$ ${subtotal.toFixed(2).replace('.', ',')}`;
            calcularTotal();
        }

        function calcularTotal() {
            const produtos = document.querySelectorAll('.produto-item');
            let total = 0;

            produtos.forEach(produto => {
                const metragem = parseFloat(produto.querySelector('input[name="metragem"]').value) || 0;
                const preco = parseFloat(produto.querySelector('input[name="preco"]').value) || 0;
                total += metragem * preco;
            });

            document.getElementById('valorTotal').textContent = total.toFixed(2).replace('.', ',');
        }

        // ========== CONTADOR DE CARACTERES ==========
        document.getElementById('observacoes').addEventListener('input', function () {
            const contador = document.getElementById('contadorCaracteres');
            contador.textContent = this.value.length;
        });

        // ========== ENVIO DO FORMULÁRIO ==========
        document.getElementById('pedidoForm').addEventListener('submit', function (e) {
            e.preventDefault();

            if (!validarFormulario()) {
                return;
            }

            const dados = coletarDados();
            enviarPedido(dados);
        });

        function validarFormulario() {
            const produtos = document.querySelectorAll('.produto-item');
            if (produtos.length === 0) {
                alert('Adicione pelo menos um produto!');
                return false;
            }

            const tabelaPrecos = document.querySelector('input[name="tabelaPrecos"]:checked');
            if (!tabelaPrecos) {
                alert('Selecione uma tabela de preços!');
                return false;
            }

            const tipoPedido = document.getElementById('tipoPedido').value;
            const numeroOP = document.getElementById('numeroOP').value;
            if (tipoPedido === 'OP' && !numeroOP.trim()) {
                alert('Número da OP é obrigatório para tipo de pedido OP!');
                document.getElementById('numeroOP').focus();
                return false;
            }

            return true;
        }

        function coletarDados() {
            const produtos = [];
            document.querySelectorAll('.produto-item').forEach(produto => {
                const artigo = produto.querySelector('input[name="artigo"]').value;
                const codigo = produto.querySelector('input[name="codigo"]').value;
                const desenho_cor = produto.querySelector('input[name="desenho_cor"]').value;
                const metragem = parseFloat(produto.querySelector('input[name="metragem"]').value);
                const preco = parseFloat(produto.querySelector('input[name="preco"]').value);

                produtos.push({
                    artigo,
                    codigo,
                    desenho_cor,
                    metragem,
                    preco,
                    subtotal: metragem * preco
                });
            });

            return {
                nomeRepresentante: document.getElementById('nomeRepresentante').value,
                razaoSocial: document.getElementById('razaoSocial').value,
                cnpj: document.getElementById('cnpj').value,
                telefone: document.getElementById('telefone').value,
                prazoPagamento: document.getElementById('prazoPagamento').value,
                tipoPedido: document.getElementById('tipoPedido').value,
                numeroOP: document.getElementById('numeroOP').value,
                tipoFrete: document.getElementById('tipoFrete').value,
                transportadoraFOB: document.getElementById('transportadoraFOB').value,
                transportadoraCIF: document.getElementById('transportadoraCIF').value,
                vendaTriangular: document.getElementById('vendaTriangular').value,
                dadosTriangulacao: document.getElementById('dadosTriangulacao').value,
                regimeRET: document.getElementById('regimeRET').value,
                tipoProduto: document.getElementById('tipoProduto').value,
                tabelaPrecos: document.querySelector('input[name="tabelaPrecos"]:checked')?.value,
                produtos: produtos,
                valorTotal: produtos.reduce((sum, p) => sum + p.subtotal, 0),
                observacoes: document.getElementById('observacoes').value
            };
        }

        function enviarPedido(dados) {
            const btnEnviar = document.querySelector('button[type="submit"]');
            btnEnviar.disabled = true;
            btnEnviar.innerHTML = '⏳ Enviando...';

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
                        alert(`✅ ${data.message}`);
                        limparFormulario();
                    } else {
                        alert(`❌ Erro: ${data.message}`);
                    }
                })
                .catch(error => {
                    console.error('Erro:', error);
                    alert('❌ Erro ao enviar pedido. Tente novamente.');
                })
                .finally(() => {
                    btnEnviar.disabled = false;
                    btnEnviar.innerHTML = '📤 Enviar Pedido';
                });
        }

        function limparFormulario() {
            document.getElementById('pedidoForm').reset();
            document.getElementById('produtos-container').innerHTML = '';
            document.getElementById('valorTotal').textContent = '0,00';
            document.getElementById('contadorCaracteres').textContent = '0';
            contadorProdutos = 0;
            limparDadosCliente();
        }

        // Adicionar primeiro produto ao carregar
        window.addEventListener('load', function () {
            adicionarProduto();
        });
    </script>
</body>

</html>
    ''', prazos=prazos)

# API ENDPOINTS


@app.route('/api/buscar_clientes')
def api_buscar_clientes():
    """API para buscar clientes (autocomplete)"""
    query = request.args.get('q', '').strip()

    if len(query) < 1:
        return jsonify([])

    clientes = buscar_clientes_por_texto(query)
    return jsonify(clientes)


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Endpoint para salvar pedido"""
    try:
        dados = request.get_json()

        if not dados:
            return jsonify({
                'success': False,
                'message': 'Dados não recebidos'
            })

        print(f"📝 Recebendo pedido de {dados.get('nomeRepresentante', 'N/A')}")
        print(f"👥 Cliente: {dados.get('razaoSocial', 'N/A')}")
        print(f"💰 Valor total: R$ {dados.get('valorTotal', 0)}")

        resultado = salvar_pedido(dados)
        return jsonify(resultado)

    except Exception as e:
        print(f"❌ Erro no endpoint submit_pedido: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        })


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
    """Listar todos os clientes"""
    conn = conectar_postgresql()
    if not conn:
        return jsonify({'erro': 'Erro de conexão'})

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cnpj, razao_social, nome_fantasia, telefone FROM clientes ORDER BY razao_social")
        clientes = cursor.fetchall()
        cursor.close()
        conn.close()

        clientes_json = []
        for cliente in clientes:
            clientes_json.append({
                'cnpj': cliente[0],
                'razao_social': cliente[1],
                'nome_fantasia': cliente[2],
                'telefone': cliente[3]
            })

        return jsonify({
            'clientes': clientes_json,
            'total': len(clientes_json)
        })
    except Exception as e:
        return jsonify({'erro': f'Erro ao buscar clientes: {e}'})


@app.route('/pedidos')
def listar_pedidos():
    """Listar pedidos para Power BI"""
    conn = conectar_postgresql()
    if not conn:
        return jsonify({'erro': 'Erro de conexão'})

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                numero_pedido, cnpj_cliente, razao_social_cliente, 
                representante, valor_total, created_at,
                tipo_pedido, tipo_produto, tabela_precos, status
            FROM pedidos 
            ORDER BY created_at DESC
            LIMIT 100
        """)
        pedidos = cursor.fetchall()
        cursor.close()
        conn.close()

        pedidos_json = []
        for pedido in pedidos:
            pedidos_json.append({
                'numero_pedido': pedido[0],
                'cnpj_cliente': pedido[1],
                'razao_social_cliente': pedido[2],
                'representante': pedido[3],
                'valor_total': float(pedido[4]) if pedido[4] else 0,
                'data_criacao': pedido[5].isoformat() if pedido[5] else None,
                'tipo_pedido': pedido[6],
                'tipo_produto': pedido[7],
                'tabela_precos': pedido[8],
                'status': pedido[9]
            })

        return jsonify({
            'pedidos': pedidos_json,
            'total': len(pedidos_json)
        })
    except Exception as e:
        return jsonify({'erro': f'Erro ao buscar pedidos: {e}'})


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


@app.route('/pedidos', methods=['POST'])
def criar_pedido():
    """Criar novo pedido"""
    try:
        data = request.get_json()

        # Validar dados obrigatórios
        if not data.get('cnpj_cliente'):
            return jsonify({'erro': 'CNPJ do cliente é obrigatório'}), 400

        # Obter próximo número
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return jsonify({'erro': 'Erro ao gerar número do pedido'}), 500

        # Buscar dados do cliente
        conn = conectar_postgresql()
        if not conn:
            return jsonify({'erro': 'Erro de conexão com banco'}), 500

        cursor = conn.cursor()

        # Buscar cliente
        cursor.execute("""
            SELECT razao_social, nome_fantasia 
            FROM clientes 
            WHERE cnpj = %s
        """, (data['cnpj_cliente'],))

        cliente = cursor.fetchone()
        if not cliente:
            cursor.close()
            conn.close()
            return jsonify({'erro': 'Cliente não encontrado'}), 404

        razao_social, nome_fantasia = cliente

        # Inserir pedido
        cursor.execute("""
            INSERT INTO pedidos 
            (numero_pedido, cnpj_cliente, razao_social_cliente, nome_fantasia_cliente, 
             representante, observacoes, itens_json, valor_total) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero_pedido,
            data['cnpj_cliente'],
            razao_social,
            nome_fantasia,
            data.get('representante', ''),
            data.get('observacoes', ''),
            str(data.get('itens', [])),  # Converter para JSON string
            float(data.get('valor_total', 0))
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'sucesso': True,
            'numero_pedido': numero_pedido,
            'mensagem': f'Pedido {numero_pedido} criado com sucesso!'
        })

    except Exception as e:
        print(f"Erro ao criar pedido: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return jsonify({'erro': f'Erro ao criar pedido: {str(e)}'}), 500


@app.route('/pedidos/<numero_pedido>')
def obter_pedido(numero_pedido):
    """Obter pedido específico"""
    try:
        conn = conectar_postgresql()
        if not conn:
            return jsonify({'erro': 'Erro de conexão com banco'}), 500

        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                id, numero_pedido, cnpj_cliente, razao_social_cliente,
                nome_fantasia_cliente, representante, observacoes, 
                itens_json, valor_total, created_at
            FROM pedidos 
            WHERE numero_pedido = %s
        """, (numero_pedido,))

        pedido = cursor.fetchone()
        cursor.close()
        conn.close()

        if not pedido:
            return jsonify({'erro': 'Pedido não encontrado'}), 404

        return jsonify({
            'id': pedido[0],
            'numero_pedido': pedido[1],
            'cnpj_cliente': pedido[2],
            'razao_social_cliente': pedido[3],
            'nome_fantasia_cliente': pedido[4],
            'representante': pedido[5],
            'observacoes': pedido[6],
            'itens': pedido[7],  # JSON string dos itens
            'valor_total': float(pedido[8]) if pedido[8] else 0,
            'created_at': pedido[9].isoformat() if pedido[9] else None
        })

    except Exception as e:
        print(f"Erro ao buscar pedido: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return jsonify({'erro': f'Erro ao buscar pedido: {str(e)}'}), 500


if __name__ == '__main__':
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Sistema Completo de Pedidos")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("📋 Formulário de Pedidos: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 API Clientes: http://127.0.0.1:5001/clientes")
        print("📦 API Pedidos: http://127.0.0.1:5001/pedidos")
        print("-" * 60)

        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
