import os
import sys
import locale
import psycopg2
import json
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

        # Tabela pedidos - VERSÃO COMPLETA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                representante VARCHAR(100),
                observacoes TEXT,
                valor_total DECIMAL(10,2) DEFAULT 0,
                data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'PENDENTE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela itens_pedido - NOVA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) REFERENCES pedidos(numero_pedido),
                artigo VARCHAR(100),
                quantidade INTEGER,
                preco_unitario DECIMAL(10,2),
                subtotal DECIMAL(10,2),
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
            ('22.333.444/0001-55', 'LOJA MATRIZ TECIDOS LTDA',
             'LOJA MATRIZ', '11999990004'),
            ('33.444.555/0001-66', 'ATACADO PREMIUM SA',
             'ATACADO PREMIUM', '11999990005')
        ]

        for cnpj, razao, fantasia, telefone in clientes:
            cursor.execute("""
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (cnpj) DO NOTHING
            """, (cnpj, razao, fantasia, telefone))

        conn.commit()
        print("✅ Clientes iniciais inseridos!")

        # Preços ampliados
        print("📋 Inserindo preços iniciais...")

        precos_normal = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D',
             15.30, 14.60, 13.90, 13.50),
            ('LYCRA COTTON', 'LYC001', 'Tecido lycra cotton',
             18.90, 18.20, 17.50, 17.00),
            ('VISCOSE LISO', 'VIS100', 'Tecido viscose liso',
             22.40, 21.70, 21.00, 20.50),
            ('JEANS STONE', 'JEN200', 'Tecido jeans stone wash',
             25.80, 25.10, 24.40, 23.90)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos_normal:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        # Preços LD
        precos_ld = [
            ('ALGODAO 30/1 LD', 'ALG301LD',
             'Tecido algodao 30/1 linha dura', 11.20, 10.50, 9.90, 9.60),
            ('POLIESTER 150D LD', 'POL150LD',
             'Tecido poliester 150D linha dura', 13.80, 13.10, 12.40, 12.00)
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


def buscar_precos():
    """Buscar todos os preços (normal + LD)"""
    conn = conectar_postgresql()
    if not conn:
        return {'normal': [], 'ld': []}

    try:
        cursor = conn.cursor()

        # Preços normais
        cursor.execute(
            "SELECT artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg FROM precos_normal ORDER BY artigo")
        precos_normal = cursor.fetchall()

        # Preços LD
        cursor.execute(
            "SELECT artigo, codigo, descricao, icms_18_ld, icms_12_ld, icms_7_ld, ret_ld_mg FROM precos_ld ORDER BY artigo")
        precos_ld = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            'normal': precos_normal,
            'ld': precos_ld
        }
    except Exception as e:
        print(f"Erro ao buscar preços: {e}")
        if conn:
            conn.close()
        return {'normal': [], 'ld': []}


def salvar_pedido(dados_pedido):
    """Salvar pedido no PostgreSQL"""
    conn = conectar_postgresql()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Inserir pedido principal
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, representante, observacoes, valor_total) 
            VALUES (%s, %s, %s, %s, %s)
        """, (
            dados_pedido['numero_pedido'],
            dados_pedido['cnpj_cliente'],
            dados_pedido['representante'],
            dados_pedido['observacoes'],
            float(dados_pedido['valor_total'])
        ))

        # Inserir itens do pedido
        for item in dados_pedido['itens']:
            cursor.execute("""
                INSERT INTO itens_pedido (numero_pedido, artigo, quantidade, preco_unitario, subtotal) 
                VALUES (%s, %s, %s, %s, %s)
            """, (
                dados_pedido['numero_pedido'],
                item['artigo'],
                int(item['quantidade']),
                float(item['preco']),
                float(item['subtotal'])
            ))

        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Pedido {dados_pedido['numero_pedido']} salvo com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


# FLASK APP
app = Flask(__name__)


@app.route('/')
def home():
    """Página principal com formulário de pedidos"""
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
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 1200px;
            margin: 0 auto;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .content {
            padding: 30px;
        }
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        .form-section {
            background: #f8f9ff;
            padding: 25px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        .form-section h3 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.3em;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: all 0.3s ease;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .items-section {
            background: #fff;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 30px;
        }
        .items-section h3 {
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        .item-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr auto;
            gap: 15px;
            margin-bottom: 15px;
            align-items: end;
        }
        .btn {
            background: #667eea;
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
        }
        .btn:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn-danger {
            background: #e74c3c;
            padding: 8px 12px;
            font-size: 0.9em;
        }
        .btn-danger:hover {
            background: #c0392b;
        }
        .btn-success {
            background: #27ae60;
            font-size: 1.2em;
            padding: 15px 40px;
        }
        .btn-success:hover {
            background: #229954;
        }
        .total-section {
            background: #e8f5e8;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: right;
        }
        .total-section h3 {
            color: #27ae60;
            font-size: 1.5em;
        }
        .actions {
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 600;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
            .item-row {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            .actions {
                flex-direction: column;
            }
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏭 DESIGNTEX TECIDOS</h1>
            <p>Sistema de Pedidos - PostgreSQL Railway</p>
        </div>

        <div class="content">
            <div id="alertContainer"></div>

            <form id="pedidoForm">
                <div class="form-grid">
                    <!-- DADOS DO PEDIDO -->
                    <div class="form-section">
                        <h3>📋 Dados do Pedido</h3>
                        
                        <div class="form-group">
                            <label for="numeroPedido">Número do Pedido:</label>
                            <input type="text" id="numeroPedido" name="numeroPedido" readonly style="background: #f0f0f0;">
                        </div>

                        <div class="form-group">
                            <label for="representante">Representante:</label>
                            <input type="text" id="representante" name="representante" required>
                        </div>

                        <div class="form-group">
                            <label for="observacoes">Observações:</label>
                            <textarea id="observacoes" name="observacoes" rows="4" placeholder="Observações gerais do pedido..."></textarea>
                        </div>
                    </div>

                    <!-- DADOS DO CLIENTE -->
                    <div class="form-section">
                        <h3>👤 Dados do Cliente</h3>
                        
                        <div class="form-group">
                            <label for="clienteSelect">Selecionar Cliente:</label>
                            <select id="clienteSelect" name="clienteSelect" required>
                                <option value="">Carregando clientes...</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label for="cnpjCliente">CNPJ:</label>
                            <input type="text" id="cnpjCliente" name="cnpjCliente" readonly style="background: #f0f0f0;">
                        </div>

                        <div class="form-group">
                            <label for="razaoSocial">Razão Social:</label>
                            <input type="text" id="razaoSocial" name="razaoSocial" readonly style="background: #f0f0f0;">
                        </div>
                    </div>
                </div>

                <!-- ITENS DO PEDIDO -->
                <div class="items-section">
                    <h3>🛒 Itens do Pedido</h3>
                    
                    <div class="item-row">
                        <label style="font-weight: 600;">Artigo/Tecido</label>
                        <label style="font-weight: 600;">Quantidade</label>
                        <label style="font-weight: 600;">Preço Unit.</label>
                        <label style="font-weight: 600;">Subtotal</label>
                        <label style="font-weight: 600;">Ação</label>
                    </div>

                    <div id="itensContainer">
                        <!-- Itens serão adicionados aqui -->
                    </div>

                    <button type="button" class="btn" onclick="adicionarItem()">➕ Adicionar Item</button>
                </div>

                <!-- TOTAL -->
                <div class="total-section">
                    <h3>💰 Total do Pedido: R$ <span id="totalPedido">0,00</span></h3>
                </div>

                <!-- AÇÕES -->
                <div class="actions">
                    <button type="button" class="btn" onclick="novaVenda()">🆕 Nova Venda</button>
                    <button type="submit" class="btn btn-success">💾 Salvar Pedido</button>
                    <button type="button" class="btn" onclick="window.open('/health', '_blank')">🔍 Status Sistema</button>
                </div>
            </form>

            <div class="loading" id="loadingDiv">
                <div class="spinner"></div>
                <p>Processando pedido...</p>
            </div>
        </div>
    </div>

    <script>
        let itemCount = 0;
        let clientes = [];
        let precos = {};

        // Carregar dados iniciais
        window.onload = function() {
            carregarNumeroPedido();
            carregarClientes();
            carregarPrecos();
            adicionarItem();
        };

        // FUNÇÕES DE CARREGAMENTO
        async function carregarNumeroPedido() {
            try {
                const response = await fetch('/api/proximo-numero');
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
                
                const select = document.getElementById('clienteSelect');
                select.innerHTML = '<option value="">Selecione um cliente...</option>';
                
                clientes.forEach(cliente => {
                    const option = document.createElement('option');
                    option.value = cliente.cnpj;
                    option.textContent = `${cliente.razao_social} - ${cliente.cnpj}`;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Erro ao carregar clientes:', error);
                mostrarAlerta('Erro ao carregar clientes', 'error');
            }
        }

        async function carregarPrecos() {
            try {
                const response = await fetch('/api/precos-completos');
                const data = await response.json();
                precos = data;
            } catch (error) {
                console.error('Erro ao carregar preços:', error);
            }
        }

        // FUNÇÕES DE CLIENTE
        function clienteSelecionado() {
            const cnpj = document.getElementById('clienteSelect').value;
            const cliente = clientes.find(c => c.cnpj === cnpj);
            
            if (cliente) {
                document.getElementById('cnpjCliente').value = cliente.cnpj;
                document.getElementById('razaoSocial').value = cliente.razao_social;
            } else {
                document.getElementById('cnpjCliente').value = '';
                document.getElementById('razaoSocial').value = '';
            }
        }

        // FUNÇÕES DE ITENS
        function adicionarItem() {
            itemCount++;
            const container = document.getElementById('itensContainer');
            
            const itemDiv = document.createElement('div');
            itemDiv.className = 'item-row';
            itemDiv.id = `item_${itemCount}`;
            
            itemDiv.innerHTML = `
                <select name="artigo_${itemCount}" onchange="precoSelecionado(${itemCount})" required>
                    <option value="">Selecione um artigo...</option>
                    <optgroup label="Preços Normais">
                        ${precos.normal ? precos.normal.map(p => 
                            `<option value="${p.artigo}" data-preco18="${p.icms_18}" data-preco12="${p.icms_12}" data-preco7="${p.icms_7}">${p.artigo} - ${p.descricao}</option>`
                        ).join('') : ''}
                    </optgroup>
                    <optgroup label="Linha Dura">
                        ${precos.ld ? precos.ld.map(p => 
                            `<option value="${p.artigo}" data-preco18="${p.icms_18_ld}" data-preco12="${p.icms_12_ld}" data-preco7="${p.icms_7_ld}">${p.artigo} - ${p.descricao}</option>`
                        ).join('') : ''}
                    </optgroup>
                </select>
                <input type="number" name="quantidade_${itemCount}" min="1" onchange="calcularSubtotal(${itemCount})" required>
                <input type="number" name="preco_${itemCount}" step="0.01" min="0" onchange="calcularSubtotal(${itemCount})" required>
                <input type="text" name="subtotal_${itemCount}" readonly style="background: #f0f0f0;">
                <button type="button" class="btn btn-danger" onclick="removerItem(${itemCount})">🗑️</button>
            `;
            
            container.appendChild(itemDiv);
        }

        function removerItem(id) {
            const item = document.getElementById(`item_${id}`);
            if (item) {
                item.remove();
                calcularTotal();
            }
        }

        function precoSelecionado(itemId) {
            const select = document.querySelector(`select[name="artigo_${itemId}"]`);
            const precoInput = document.querySelector(`input[name="preco_${itemId}"]`);
            
            if (select.selectedIndex > 0) {
                const option = select.selectedOptions[0];
                // Usar preço ICMS 18% como padrão
                const preco = option.getAttribute('data-preco18');
                if (preco) {
                    precoInput.value = parseFloat(preco).toFixed(2);
                    calcularSubtotal(itemId);
                }
            }
        }

        function calcularSubtotal(itemId) {
            const quantidade = document.querySelector(`input[name="quantidade_${itemId}"]`).value;
            const preco = document.querySelector(`input[name="preco_${itemId}"]`).value;
            const subtotalInput = document.querySelector(`input[name="subtotal_${itemId}"]`);
            
            if (quantidade && preco) {
                const subtotal = parseFloat(quantidade) * parseFloat(preco);
                subtotalInput.value = `R$ ${subtotal.toFixed(2).replace('.', ',')}`;
            } else {
                subtotalInput.value = '';
            }
            
            calcularTotal();
        }

        function calcularTotal() {
            let total = 0;
            const subtotals = document.querySelectorAll('input[name^="subtotal_"]');
            
            subtotals.forEach(input => {
                if (input.value) {
                    const valor = input.value.replace('R$ ', '').replace(',', '.');
                    total += parseFloat(valor) || 0;
                }
            });
            
            document.getElementById('totalPedido').textContent = total.toFixed(2).replace('.', ',');
        }

        // FUNÇÕES DE FORMULÁRIO
        function novaVenda() {
            if (confirm('Limpar formulário e iniciar nova venda?')) {
                document.getElementById('pedidoForm').reset();
                document.getElementById('itensContainer').innerHTML = '';
                itemCount = 0;
                carregarNumeroPedido();
                adicionarItem();
                document.getElementById('totalPedido').textContent = '0,00';
            }
        }

        // FUNÇÕES DE ALERTA
        function mostrarAlerta(mensagem, tipo) {
            const container = document.getElementById('alertContainer');
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${tipo}`;
            alertDiv.textContent = mensagem;
            
            container.innerHTML = '';
            container.appendChild(alertDiv);
            
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }

        // SUBMISSÃO DO FORMULÁRIO
        document.getElementById('pedidoForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Validações
            if (!document.getElementById('clienteSelect').value) {
                mostrarAlerta('Selecione um cliente!', 'error');
                return;
            }

            if (!document.getElementById('representante').value.trim()) {
                mostrarAlerta('Informe o representante!', 'error');
                return;
            }

            // Coletar itens
            const itens = [];
            for (let i = 1; i <= itemCount; i++) {
                const artigo = document.querySelector(`select[name="artigo_${i}"]`);
                const quantidade = document.querySelector(`input[name="quantidade_${i}"]`);
                const preco = document.querySelector(`input[name="preco_${i}"]`);
                
                if (artigo && artigo.value && quantidade && quantidade.value && preco && preco.value) {
                    const subtotal = parseFloat(quantidade.value) * parseFloat(preco.value);
                    itens.push({
                        artigo: artigo.value,
                        quantidade: quantidade.value,
                        preco: preco.value,
                        subtotal: subtotal.toFixed(2)
                    });
                }
            }

            if (itens.length === 0) {
                mostrarAlerta('Adicione pelo menos um item ao pedido!', 'error');
                return;
            }

            // Calcular total
            const valorTotal = itens.reduce((total, item) => total + parseFloat(item.subtotal), 0);

            // Preparar dados
            const dadosPedido = {
                numero_pedido: document.getElementById('numeroPedido').value,
                cnpj_cliente: document.getElementById('cnpjCliente').value,
                representante: document.getElementById('representante').value,
                observacoes: document.getElementById('observacoes').value,
                valor_total: valorTotal.toFixed(2),
                itens: itens
            };

            // Mostrar loading
            document.getElementById('loadingDiv').style.display = 'block';
            
            try {
                const response = await fetch('/api/salvar-pedido', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(dadosPedido)
                });

                const result = await response.json();

                if (response.ok) {
                    mostrarAlerta(`Pedido ${dadosPedido.numero_pedido} salvo com sucesso!`, 'success');
                    
                    // Perguntar se quer gerar PDF
                    if (confirm('Pedido salvo! Deseja gerar o PDF?')) {
                        window.open(`/api/gerar-pdf/${dadosPedido.numero_pedido}`, '_blank');
                    }
                    
                    // Limpar formulário após 2 segundos
                    setTimeout(() => {
                        novaVenda();
                    }, 2000);
                } else {
                    mostrarAlerta(result.erro || 'Erro ao salvar pedido', 'error');
                }
            } catch (error) {
                console.error('Erro:', error);
                mostrarAlerta('Erro de conexão ao salvar pedido', 'error');
            } finally {
                document.getElementById('loadingDiv').style.display = 'none';
            }
        });

        // Event listeners
        document.getElementById('clienteSelect').addEventListener('change', clienteSelecionado);
    </script>
</body>
</html>
    ''')

# APIs


@app.route('/api/proximo-numero')
def api_proximo_numero():
    """API para obter próximo número de pedido"""
    numero = obter_proximo_numero_pedido()
    if numero:
        return jsonify({'numero': numero})
    else:
        return jsonify({'erro': 'Erro ao gerar número'}), 500


@app.route('/api/precos-completos')
def api_precos_completos():
    """API para obter todos os preços"""
    precos_data = buscar_precos()

    # Formatar para JSON
    result = {
        'normal': [],
        'ld': []
    }

    for preco in precos_data['normal']:
        result['normal'].append({
            'artigo': preco[0],
            'codigo': preco[1],
            'descricao': preco[2],
            'icms_18': float(preco[3]) if preco[3] else 0,
            'icms_12': float(preco[4]) if preco[4] else 0,
            'icms_7': float(preco[5]) if preco[5] else 0,
            'ret_mg': float(preco[6]) if preco[6] else 0
        })

    for preco in precos_data['ld']:
        result['ld'].append({
            'artigo': preco[0],
            'codigo': preco[1],
            'descricao': preco[2],
            'icms_18_ld': float(preco[3]) if preco[3] else 0,
            'icms_12_ld': float(preco[4]) if preco[4] else 0,
            'icms_7_ld': float(preco[5]) if preco[5] else 0,
            'ret_ld_mg': float(preco[6]) if preco[6] else 0
        })

    return jsonify(result)


@app.route('/api/salvar-pedido', methods=['POST'])
def api_salvar_pedido():
    """API para salvar pedido"""
    try:
        dados = request.json

        if salvar_pedido(dados):
            return jsonify({'status': 'success', 'numero_pedido': dados['numero_pedido']})
        else:
            return jsonify({'erro': 'Erro ao salvar no banco de dados'}), 500

    except Exception as e:
        print(f"Erro na API salvar pedido: {e}")
        return jsonify({'erro': str(e)}), 500


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
                'environment': os.getenv('ENVIRONMENT', 'development'),
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
    precos_data = buscar_precos()
    precos_json = []

    for preco in precos_data['normal']:
        precos_json.append({
            'tipo': 'normal',
            'artigo': preco[0],
            'codigo': preco[1],
            'descricao': preco[2],
            'icms_18': float(preco[3]) if preco[3] else 0,
            'icms_12': float(preco[4]) if preco[4] else 0,
            'icms_7': float(preco[5]) if preco[5] else 0,
            'ret_mg': float(preco[6]) if preco[6] else 0
        })

    for preco in precos_data['ld']:
        precos_json.append({
            'tipo': 'ld',
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


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Sistema Completo")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/precos")
        print("-" * 50)

        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
