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
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                quantidade INTEGER,
                valor_unitario DECIMAL(10,2),
                valor_total DECIMAL(10,2),
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
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 40/1', 'VIS401', 'Tecido viscose 40/1',
             18.90, 17.80, 17.20, 16.90),
            ('ELASTANO 220G', 'ELA220', 'Tecido elastano 220g',
             22.50, 21.30, 20.90, 20.50)
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


def salvar_pedido(dados_pedido):
    """Salvar pedido no banco"""
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
            dados_pedido['valor_total']
        ))

        # Inserir itens do pedido
        for item in dados_pedido['itens']:
            cursor.execute("""
                INSERT INTO itens_pedido (numero_pedido, artigo, codigo, descricao, quantidade, valor_unitario, valor_total) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                dados_pedido['numero_pedido'],
                item['artigo'],
                item['codigo'],
                item['descricao'],
                item['quantidade'],
                item['valor_unitario'],
                item['valor_total']
            ))

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


# FLASK APP
app = Flask(__name__)


@app.route('/')
def home():
    """Página inicial com sistema completo de pedidos"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DESIGNTEX TECIDOS - Sistema de Pedidos</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .header {
            background: rgba(255,255,255,0.95);
            padding: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 20px;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .logo h1 {
            color: #667eea;
            font-size: 1.8em;
            font-weight: 700;
        }

        .status-badge {
            background: #10b981;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
        }

        .container {
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f1f5f9;
        }

        .card-title {
            font-size: 1.5em;
            color: #1e293b;
            font-weight: 600;
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
            font-weight: 600;
            color: #374151;
            margin-bottom: 8px;
        }

        input, select, textarea {
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s ease;
        }

        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
        }

        textarea {
            resize: vertical;
            min-height: 100px;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: #667eea;
            color: white;
        }

        .btn-primary:hover {
            background: #5a67d8;
            transform: translateY(-1px);
        }

        .btn-success {
            background: #10b981;
            color: white;
        }

        .btn-success:hover {
            background: #059669;
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: #64748b;
            color: white;
        }

        .btn-secondary:hover {
            background: #475569;
        }

        .btn-danger {
            background: #ef4444;
            color: white;
        }

        .btn-danger:hover {
            background: #dc2626;
        }

        .table-container {
            overflow-x: auto;
            margin-top: 20px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }

        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }

        th {
            background: #f8fafc;
            font-weight: 600;
            color: #374151;
        }

        tr:hover {
            background: #f8fafc;
        }

        .total-section {
            background: #f8fafc;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }

        .total-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 1.1em;
        }

        .total-final {
            font-weight: 700;
            font-size: 1.3em;
            color: #667eea;
            border-top: 2px solid #667eea;
            padding-top: 10px;
        }

        .alert {
            padding: 16px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 500;
        }

        .alert-success {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }

        .alert-danger {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }

        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }

        .modal-content {
            background-color: white;
            margin: 10% auto;
            padding: 30px;
            border-radius: 12px;
            width: 90%;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
        }

        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }

        .close:hover {
            color: #000;
        }

        .footer-note {
            background: #fef3c7;
            border: 1px solid #fbbf24;
            color: #92400e;
            padding: 16px;
            border-radius: 8px;
            margin-top: 20px;
            font-weight: 500;
            text-align: center;
        }

        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .header-content {
                flex-direction: column;
                gap: 15px;
            }
            
            .card {
                margin: 20px 10px;
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo">
                <h1>🏭 DESIGNTEX TECIDOS</h1>
            </div>
            <div class="status-badge">
                ✅ Sistema Online
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Formulário de Pedido -->
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📋 Novo Pedido de Venda</h2>
                <button class="btn btn-secondary" onclick="carregarClientes()">
                    🔄 Atualizar Dados
                </button>
            </div>

            <form id="formPedido">
                <div class="form-grid">
                    <div class="form-group">
                        <label for="cliente">Cliente *</label>
                        <select id="cliente" name="cliente" required>
                            <option value="">Selecione o cliente...</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="representante">Representante *</label>
                        <input type="text" id="representante" name="representante" required 
                               placeholder="Nome do representante">
                    </div>

                    <div class="form-group full-width">
                        <label for="observacoes">Observações</label>
                        <textarea id="observacoes" name="observacoes" 
                                  placeholder="Informações adicionais sobre o pedido..."></textarea>
                    </div>
                </div>

                <!-- Seção de Itens -->
                <div class="card-header">
                    <h3>🛍️ Itens do Pedido</h3>
                    <button type="button" class="btn btn-primary" onclick="adicionarItem()">
                        ➕ Adicionar Item
                    </button>
                </div>

                <div class="table-container">
                    <table id="tabelaItens">
                        <thead>
                            <tr>
                                <th>Artigo</th>
                                <th>Código</th>
                                <th>Descrição</th>
                                <th>Qtd</th>
                                <th>Valor Unit.</th>
                                <th>Total</th>
                                <th>Ação</th>
                            </tr>
                        </thead>
                        <tbody id="itensCorpo">
                        </tbody>
                    </table>
                </div>

                <div class="total-section">
                    <div class="total-row">
                        <span>Total de Itens:</span>
                        <span id="totalItens">0</span>
                    </div>
                    <div class="total-row total-final">
                        <span>Valor Total:</span>
                        <span id="valorTotal">R$ 0,00</span>
                    </div>
                </div>

                <div class="footer-note">
                    ⚠️ <strong>Pedido sujeito à confirmação da empresa fornecedora.</strong>
                </div>

                <div style="margin-top: 30px; text-align: center;">
                    <button type="submit" class="btn btn-success">
                        💾 Finalizar Pedido
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="limparFormulario()">
                        🗑️ Limpar
                    </button>
                    <button type="button" class="btn btn-primary" onclick="visualizarPedido()">
                        👁️ Visualizar
                    </button>
                </div>
            </form>
        </div>

        <!-- APIs e Informações -->
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">🔗 APIs Disponíveis</h2>
            </div>
            
            <div class="form-grid">
                <a href="/health" class="btn btn-primary" target="_blank">
                    🔍 Health Check
                </a>
                <a href="/clientes" class="btn btn-primary" target="_blank">
                    👥 API Clientes
                </a>
                <a href="/precos" class="btn btn-primary" target="_blank">
                    💰 API Preços
                </a>
                <a href="/pedidos" class="btn btn-primary" target="_blank">
                    📋 API Pedidos
                </a>
            </div>
        </div>
    </div>

    <!-- Modal de Visualização -->
    <div id="modalVisualizacao" class="modal">
        <div class="modal-content">
            <span class="close" onclick="fecharModal()">&times;</span>
            <div id="conteudoModal"></div>
        </div>
    </div>

    <script>
        let clientes = [];
        let precos = [];
        let itensPedido = [];
        let contadorItens = 0;

        // Carregar dados iniciais
        document.addEventListener('DOMContentLoaded', function() {
            carregarClientes();
            carregarPrecos();
        });

        async function carregarClientes() {
            try {
                const response = await fetch('/clientes');
                const data = await response.json();
                clientes = data.clientes;
                
                const select = document.getElementById('cliente');
                select.innerHTML = '<option value="">Selecione o cliente...</option>';
                
                clientes.forEach(cliente => {
                    const option = document.createElement('option');
                    option.value = cliente.cnpj;
                    option.textContent = `${cliente.razao_social} (${cliente.cnpj})`;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Erro ao carregar clientes:', error);
            }
        }

        async function carregarPrecos() {
            try {
                const response = await fetch('/precos');
                const data = await response.json();
                precos = data.precos;
            } catch (error) {
                console.error('Erro ao carregar preços:', error);
            }
        }

        function adicionarItem() {
            contadorItens++;
            const tbody = document.getElementById('itensCorpo');
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>
                    <select onchange="atualizarPreco(${contadorItens})" id="artigo_${contadorItens}">
                        <option value="">Selecionar...</option>
                        ${precos.map(p => `<option value="${p.artigo}" data-codigo="${p.codigo}" data-descricao="${p.descricao}" data-preco="${p.icms_18}">${p.artigo}</option>`).join('')}
                    </select>
                </td>
                <td><input type="text" id="codigo_${contadorItens}" readonly></td>
                <td><input type="text" id="descricao_${contadorItens}" readonly></td>
                <td><input type="number" id="quantidade_${contadorItens}" min="1" value="1" onchange="calcularTotal(${contadorItens})"></td>
                <td><input type="number" step="0.01" id="valor_${contadorItens}" onchange="calcularTotal(${contadorItens})"></td>
                <td><span id="total_${contadorItens}">R$ 0,00</span></td>
                <td><button type="button" class="btn btn-danger" onclick="removerItem(${contadorItens})">🗑️</button></td>
            `;
            
            tbody.appendChild(tr);
        }

        function atualizarPreco(id) {
            const select = document.getElementById(`artigo_${id}`);
            const option = select.selectedOptions[0];
            
            if (option && option.dataset.codigo) {
                document.getElementById(`codigo_${id}`).value = option.dataset.codigo;
                document.getElementById(`descricao_${id}`).value = option.dataset.descricao;
                document.getElementById(`valor_${id}`).value = parseFloat(option.dataset.preco).toFixed(2);
                calcularTotal(id);
            }
        }

        function calcularTotal(id) {
            const quantidade = parseInt(document.getElementById(`quantidade_${id}`).value) || 0;
            const valor = parseFloat(document.getElementById(`valor_${id}`).value) || 0;
            const total = quantidade * valor;
            
            document.getElementById(`total_${id}`).textContent = `R$ ${total.toFixed(2).replace('.', ',')}`;
            
            atualizarTotalGeral();
        }

        function removerItem(id) {
            const tr = document.getElementById(`artigo_${id}`).closest('tr');
            tr.remove();
            atualizarTotalGeral();
        }

        function atualizarTotalGeral() {
            const tbody = document.getElementById('itensCorpo');
            const totalItens = tbody.children.length;
            let valorTotal = 0;

            for (let i = 0; i < tbody.children.length; i++) {
                const totalText = tbody.children[i].querySelector('[id^="total_"]').textContent;
                const valor = parseFloat(totalText.replace('R$ ', '').replace(',', '.')) || 0;
                valorTotal += valor;
            }

            document.getElementById('totalItens').textContent = totalItens;
            document.getElementById('valorTotal').textContent = `R$ ${valorTotal.toFixed(2).replace('.', ',')}`;
        }

        function limparFormulario() {
            document.getElementById('formPedido').reset();
            document.getElementById('itensCorpo').innerHTML = '';
            atualizarTotalGeral();
            contadorItens = 0;
        }

        function visualizarPedido() {
            // Implementar visualização do pedido
            const modal = document.getElementById('modalVisualizacao');
            const conteudo = document.getElementById('conteudoModal');
            
            conteudo.innerHTML = `
                <h2>📋 Visualização do Pedido</h2>
                <p>Funcionalidade em desenvolvimento...</p>
            `;
            
            modal.style.display = 'block';
        }

        function fecharModal() {
            document.getElementById('modalVisualizacao').style.display = 'none';
        }

        // Enviar pedido
        document.getElementById('formPedido').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const dadosPedido = {
                cliente: formData.get('cliente'),
                representante: formData.get('representante'),
                observacoes: formData.get('observacoes'),
                itens: []
            };

            // Coletar itens
            const tbody = document.getElementById('itensCorpo');
            for (let i = 0; i < tbody.children.length; i++) {
                const row = tbody.children[i];
                const artigo = row.querySelector('[id^="artigo_"]').value;
                if (artigo) {
                    dadosPedido.itens.push({
                        artigo: artigo,
                        codigo: row.querySelector('[id^="codigo_"]').value,
                        descricao: row.querySelector('[id^="descricao_"]').value,
                        quantidade: row.querySelector('[id^="quantidade_"]').value,
                        valor_unitario: row.querySelector('[id^="valor_"]').value,
                        valor_total: row.querySelector('[id^="total_"]').textContent.replace('R$ ', '').replace(',', '.')
                    });
                }
            }

            try {
                const response = await fetch('/criar-pedido', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(dadosPedido)
                });

                const result = await response.json();
                
                if (result.success) {
                    alert(`✅ Pedido ${result.numero_pedido} criado com sucesso!`);
                    limparFormulario();
                } else {
                    alert(`❌ Erro: ${result.message}`);
                }
            } catch (error) {
                console.error('Erro:', error);
                alert('❌ Erro ao enviar pedido');
            }
        });
    </script>
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
                'timestamp': datetime.now().isoformat(),
                'environment': os.getenv('ENVIRONMENT', 'development')
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


@app.route('/criar-pedido', methods=['POST'])
def criar_pedido():
    """Criar novo pedido"""
    try:
        dados = request.json

        # Validar dados obrigatórios
        if not dados.get('cliente') or not dados.get('representante'):
            return jsonify({
                'success': False,
                'message': 'Cliente e representante são obrigatórios'
            }), 400

        # Obter próximo número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return jsonify({
                'success': False,
                'message': 'Erro ao gerar número do pedido'
            }), 500

        # Calcular valor total
        valor_total = 0
        for item in dados.get('itens', []):
            valor_total += float(item.get('valor_total', 0))

        # Preparar dados do pedido
        dados_pedido = {
            'numero_pedido': numero_pedido,
            'cnpj_cliente': dados['cliente'],
            'representante': dados['representante'],
            'observacoes': dados.get('observacoes', '') + '\n\nPedido sujeito à confirmação da empresa fornecedora.',
            'valor_total': valor_total,
            'itens': dados.get('itens', [])
        }

        # Salvar no banco
        if salvar_pedido(dados_pedido):
            return jsonify({
                'success': True,
                'numero_pedido': numero_pedido,
                'message': f'Pedido {numero_pedido} criado com sucesso!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Erro ao salvar pedido no banco'
            }), 500

    except Exception as e:
        print(f"Erro ao criar pedido: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        }), 500


@app.route('/pedidos')
def listar_pedidos():
    """Listar pedidos em JSON"""
    conn = conectar_postgresql()
    if not conn:
        return jsonify({'pedidos': [], 'total': 0})

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.numero_pedido, p.cnpj_cliente, p.representante, 
                   p.valor_total, p.created_at, c.razao_social
            FROM pedidos p
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj
            ORDER BY p.created_at DESC
            LIMIT 50
        """)
        pedidos = cursor.fetchall()

        pedidos_json = []
        for pedido in pedidos:
            pedidos_json.append({
                'numero_pedido': pedido[0],
                'cnpj_cliente': pedido[1],
                'representante': pedido[2],
                'valor_total': float(pedido[3]) if pedido[3] else 0,
                'data_pedido': pedido[4].isoformat() if pedido[4] else None,
                'razao_social': pedido[5] or 'Cliente não encontrado'
            })

        cursor.close()
        conn.close()

        return jsonify({
            'pedidos': pedidos_json,
            'total': len(pedidos_json)
        })

    except Exception as e:
        print(f"Erro ao buscar pedidos: {e}")
        if conn:
            conn.close()
        return jsonify({'pedidos': [], 'total': 0, 'error': str(e)})


if __name__ == '__main__':
    # Porta dinâmica para Railway
    port = int(os.environ.get('PORT', 5001))

    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Railway Deploy")
        print(f"📡 Porta: {port}")
        print("-" * 50)

        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("❌ Falha na inicialização do banco de dados")


# if __name__ == '__main__':
# Obter porta do ambiente (Railway usa PORT)
#   port = int(os.getenv('PORT', 5001))

# Inicializar banco de dados
#  if init_database():
#      print("🚀 Iniciando DESIGNTEX TECIDOS - Sistema de Pedidos")
#      print(f"📡 Servidor rodando na porta: {port}")
#       print("🔗 Endpoints disponíveis:")
#       print("   - GET  /            - Interface principal")
#       print("   - GET  /health      - Status do sistema")
#      print("   - GET  /clientes    - API de clientes")
#      print("   - GET  /precos      - API de preços")
#      print("   - GET  /pedidos     - API de pedidos")
#      print("   - POST /criar-pedido - Criar novo pedido")
#       print("-" * 50)

#        app.run(host='0.0.0.0', port=port, debug=False)
#   else:
#       print("❌ Falha na inicialização do banco de dados")
#        print("🔧 Verifique as configurações do PostgreSQL")
#
