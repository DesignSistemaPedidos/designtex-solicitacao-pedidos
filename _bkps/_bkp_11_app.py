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

# CONFIGURAÇÃO DO BANCO DE DADOS (LOCAL E RAILWAY)


def get_database_config():
    """Obter configuração do banco baseada no ambiente"""

    environment = os.getenv('ENVIRONMENT', 'development')

    if environment == 'production':
        print("🌐 Usando RAILWAY PostgreSQL (Produção)")
        return {
            'database_url': 'postgresql://postgres:zGgADknoSZLTjavfpImTgTBAVSicvJNY@metro.proxy.rlwy.net:47441/railway'
        }
    else:
        print("🏠 Usando PostgreSQL LOCAL (Desenvolvimento)")
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

            # Se tiver DATABASE_URL (Railway)
            if 'database_url' in DATABASE_CONFIG:
                database_url = DATABASE_CONFIG['database_url']
                url_with_encoding = f"{database_url}?client_encoding={encoding}"
                conn = psycopg2.connect(url_with_encoding)
            else:
                # Configuração local
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
            print(f"📋 PostgreSQL Version: {str(resultado[0])[:50]}...")

            return conn

        except UnicodeDecodeError as e:
            print(f"❌ Erro de encoding {encoding}: {str(e)[:100]}...")
            if 'conn' in locals():
                conn.close()
            continue

        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if 'codec' in error_msg or 'decode' in error_msg:
                print(f"❌ Erro de encoding {encoding}: {error_msg[:100]}...")
                if 'conn' in locals():
                    conn.close()
                continue
            else:
                print(f"❌ Erro de conexão: {error_msg}")
                return None

        except Exception as e:
            print(f"❌ Erro geral com encoding {encoding}: {str(e)[:100]}...")
            if 'conn' in locals():
                conn.close()
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

        # Verificar tabelas existentes
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

        # Tabela pedidos com mais campos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                razao_social_cliente VARCHAR(200),
                representante VARCHAR(100),
                observacoes TEXT,
                valor_total DECIMAL(10,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'PENDENTE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela itens do pedido
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedido_itens (
                id SERIAL PRIMARY KEY,
                pedido_id INTEGER REFERENCES pedidos(id),
                numero_pedido VARCHAR(10),
                artigo VARCHAR(100),
                codigo VARCHAR(50),
                descricao VARCHAR(200),
                quantidade DECIMAL(10,2),
                preco_unitario DECIMAL(10,2),
                preco_total DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela sequencia
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

        # Clientes
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

        # Preços
        precos = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 120G', 'VIS120', 'Tecido viscose 120g',
             18.90, 18.10, 17.30, 16.90),
            ('LYCRA 180G', 'LYC180', 'Tecido lycra 180g', 22.40, 21.60, 20.80, 20.40)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        conn.commit()
        print("✅ Dados iniciais inseridos!")

    except Exception as e:
        print(f"⚠️ Erro ao inserir dados iniciais: {e}")


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
    """Salvar pedido completo no banco"""
    conn = conectar_postgresql()
    if not conn:
        return {'success': False, 'erro': 'Erro de conexão'}

    try:
        cursor = conn.cursor()

        # Obter próximo número
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return {'success': False, 'erro': 'Erro ao gerar número do pedido'}

        # Inserir pedido principal
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, razao_social_cliente, representante, observacoes, valor_total, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            numero_pedido,
            dados_pedido.get('cnpj_cliente'),
            dados_pedido.get('razao_social_cliente'),
            dados_pedido.get('representante'),
            dados_pedido.get('observacoes'),
            dados_pedido.get('valor_total', 0),
            'PENDENTE'
        ))

        pedido_id = cursor.fetchone()[0]

        # Inserir itens do pedido
        for item in dados_pedido.get('itens', []):
            cursor.execute("""
                INSERT INTO pedido_itens (pedido_id, numero_pedido, artigo, codigo, descricao, quantidade, preco_unitario, preco_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                pedido_id,
                numero_pedido,
                item.get('artigo'),
                item.get('codigo'),
                item.get('descricao'),
                item.get('quantidade', 0),
                item.get('preco_unitario', 0),
                item.get('preco_total', 0)
            ))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            'success': True,
            'numero_pedido': numero_pedido,
            'pedido_id': pedido_id
        }

    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'erro': str(e)}


# FLASK APP
app = Flask(__name__)


@app.route('/')
def home():
    """Página inicial com sistema completo"""
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
        }
        .navbar {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .navbar h1 {
            color: white;
            font-size: 1.5em;
        }
        .navbar .buttons {
            display: flex;
            gap: 10px;
        }
        .btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .btn:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }
        .btn.primary {
            background: #ff6b6b;
        }
        .btn.primary:hover {
            background: #ff5252;
        }
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            padding: 0 2rem;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
            color: #333;
        }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e1e1e1;
            border-radius: 10px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .item-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr auto;
            gap: 1rem;
            align-items: end;
            margin-bottom: 1rem;
            padding: 1rem;
            background: #f8f9ff;
            border-radius: 10px;
        }
        .btn-remove {
            background: #ff4757;
            color: white;
            border: none;
            padding: 0.75rem;
            border-radius: 8px;
            cursor: pointer;
        }
        .btn-add {
            background: #2ed573;
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1rem;
            margin: 1rem 0;
        }
        .total {
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
            text-align: right;
            margin-top: 1rem;
        }
        .status { padding: 1rem; border-radius: 10px; margin: 1rem 0; text-align: center; font-weight: bold; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <nav class="navbar">
        <h1>🏭 DESIGNTEX TECIDOS</h1>
        <div class="buttons">
            <a href="/health" class="btn">🔍 Status</a>
            <a href="/clientes" class="btn">👥 Clientes</a>
            <a href="/precos" class="btn">💰 Preços</a>
            <button onclick="showNewOrder()" class="btn primary">📝 Novo Pedido</button>
        </div>
    </nav>
    
    <div class="container">
        <!-- Seção de Novo Pedido -->
        <div id="newOrderSection" class="card">
            <h2>📝 Emitir Novo Pedido</h2>
            
            <form id="orderForm">
                <div class="grid">
                    <div class="form-group">
                        <label>Cliente (CNPJ):</label>
                        <select id="clienteSelect" required>
                            <option value="">Carregando clientes...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Representante:</label>
                        <input type="text" id="representante" placeholder="Nome do representante" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Observações:</label>
                    <textarea id="observacoes" placeholder="Observações do pedido (opcional)" rows="3"></textarea>
                </div>
                
                <h3>📦 Itens do Pedido</h3>
                <div id="itensContainer">
                    <div class="item-row">
                        <div>
                            <label>Produto:</label>
                            <select class="produto-select" required>
                                <option value="">Carregando produtos...</option>
                            </select>
                        </div>
                        <div>
                            <label>Quantidade:</label>
                            <input type="number" class="quantidade" step="0.01" min="0" placeholder="0.00" required>
                        </div>
                        <div>
                            <label>Preço Unitário:</label>
                            <input type="number" class="preco-unitario" step="0.01" min="0" placeholder="0.00" readonly>
                        </div>
                        <div>
                            <label>Total:</label>
                            <input type="number" class="preco-total" step="0.01" min="0" placeholder="0.00" readonly>
                        </div>
                        <div>
                            <button type="button" class="btn-remove" onclick="removeItem(this)">🗑️</button>
                        </div>
                    </div>
                </div>
                
                <button type="button" class="btn-add" onclick="addItem()">➕ Adicionar Item</button>
                
                <div class="total">
                    Total do Pedido: R$ <span id="totalPedido">0.00</span>
                </div>
                
                <div style="text-align: center; margin-top: 2rem;">
                    <button type="submit" class="btn primary" style="font-size: 1.2em; padding: 1rem 3rem;">
                        🚀 Emitir Pedido
                    </button>
                </div>
            </form>
        </div>
        
        <!-- Status Messages -->
        <div id="statusMessage" class="hidden"></div>
        
        <!-- Informações do Sistema -->
        <div class="card">
            <h2>📊 Sistema Online - Railway PostgreSQL</h2>
            <p>✅ Banco de dados em produção</p>
            <p>✅ API funcionando</p>
            <p>✅ Pronto para emitir pedidos</p>
        </div>
    </div>
    
    <script>
        let clientes = [];
        let precos = [];
        
        // Carregar dados iniciais
        async function loadInitialData() {
            try {
                // Carregar clientes
                const clientesRes = await fetch('/clientes');
                const clientesData = await clientesRes.json();
                clientes = clientesData.clientes;
                
                // Carregar preços
                const precosRes = await fetch('/precos');
                const precosData = await precosRes.json();
                precos = precosData.precos;
                
                updateClienteSelect();
                updateProdutoSelects();
                
            } catch (error) {
                console.error('Erro ao carregar dados:', error);
                showStatus('Erro ao carregar dados iniciais', 'error');
            }
        }
        
        function updateClienteSelect() {
            const select = document.getElementById('clienteSelect');
            select.innerHTML = '<option value="">Selecione um cliente</option>';
            
            clientes.forEach(cliente => {
                const option = document.createElement('option');
                option.value = cliente.cnpj;
                option.textContent = `${cliente.cnpj} - ${cliente.razao_social}`;
                option.dataset.razaoSocial = cliente.razao_social;
                select.appendChild(option);
            });
        }
        
        function updateProdutoSelects() {
            document.querySelectorAll('.produto-select').forEach(select => {
                select.innerHTML = '<option value="">Selecione um produto</option>';
                
                precos.forEach(preco => {
                    const option = document.createElement('option');
                    option.value = preco.codigo;
                    option.textContent = `${preco.artigo} - ${preco.descricao}`;
                    option.dataset.preco = preco.icms_18;
                    option.dataset.artigo = preco.artigo;
                    option.dataset.descricao = preco.descricao;
                    select.appendChild(option);
                });
            });
        }
        
        function addItem() {
            const container = document.getElementById('itensContainer');
            const newItem = container.firstElementChild.cloneNode(true);
            
            // Limpar valores
            newItem.querySelectorAll('input').forEach(input => input.value = '');
            newItem.querySelector('select').selectedIndex = 0;
            
            container.appendChild(newItem);
            updateProdutoSelects();
            setupItemEvents(newItem);
        }
        
        function removeItem(button) {
            const container = document.getElementById('itensContainer');
            if (container.children.length > 1) {
                button.closest('.item-row').remove();
                calculateTotal();
            }
        }
        
        function setupItemEvents(item) {
            const produtoSelect = item.querySelector('.produto-select');
            const quantidade = item.querySelector('.quantidade');
            const precoUnitario = item.querySelector('.preco-unitario');
            const precoTotal = item.querySelector('.preco-total');
            
            produtoSelect.addEventListener('change', function() {
                const selectedOption = this.options[this.selectedIndex];
                if (selectedOption.dataset.preco) {
                    precoUnitario.value = selectedOption.dataset.preco;
                    calculateItemTotal(item);
                }
            });
            
            quantidade.addEventListener('input', () => calculateItemTotal(item));
        }
        
        function calculateItemTotal(item) {
            const quantidade = parseFloat(item.querySelector('.quantidade').value) || 0;
            const precoUnitario = parseFloat(item.querySelector('.preco-unitario').value) || 0;
            const precoTotal = item.querySelector('.preco-total');
            
            const total = quantidade * precoUnitario;
            precoTotal.value = total.toFixed(2);
            
            calculateTotal();
        }
        
        function calculateTotal() {
            let total = 0;
            document.querySelectorAll('.preco-total').forEach(input => {
                total += parseFloat(input.value) || 0;
            });
            
            document.getElementById('totalPedido').textContent = total.toFixed(2);
        }
        
        function showStatus(message, type) {
            const statusDiv = document.getElementById('statusMessage');
            statusDiv.className = `status ${type}`;
            statusDiv.textContent = message;
            statusDiv.classList.remove('hidden');
            
            setTimeout(() => {
                statusDiv.classList.add('hidden');
            }, 5000);
        }
        
        function showNewOrder() {
            document.getElementById('newOrderSection').scrollIntoView({ behavior: 'smooth' });
        }
        
        // Setup form submission
        document.getElementById('orderForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const clienteSelect = document.getElementById('clienteSelect');
            const selectedOption = clienteSelect.options[clienteSelect.selectedIndex];
            
            if (!selectedOption.value) {
                showStatus('Selecione um cliente', 'error');
                return;
            }
            
            const itens = [];
            document.querySelectorAll('.item-row').forEach(row => {
                const produtoSelect = row.querySelector('.produto-select');
                const produtoOption = produtoSelect.options[produtoSelect.selectedIndex];
                const quantidade = parseFloat(row.querySelector('.quantidade').value) || 0;
                const precoUnitario = parseFloat(row.querySelector('.preco-unitario').value) || 0;
                const precoTotal = parseFloat(row.querySelector('.preco-total').value) || 0;
                
                if (produtoOption.value && quantidade > 0) {
                    itens.push({
                        artigo: produtoOption.dataset.artigo,
                        codigo: produtoOption.value,
                        descricao: produtoOption.dataset.descricao,
                        quantidade: quantidade,
                        preco_unitario: precoUnitario,
                        preco_total: precoTotal
                    });
                }
            });
            
            if (itens.length === 0) {
                showStatus('Adicione pelo menos um item ao pedido', 'error');
                return;
            }
            
            const pedidoData = {
                cnpj_cliente: selectedOption.value,
                razao_social_cliente: selectedOption.dataset.razaoSocial,
                representante: document.getElementById('representante').value,
                observacoes: document.getElementById('observacoes').value,
                valor_total: parseFloat(document.getElementById('totalPedido').textContent),
                itens: itens
            };
            
            try {
                const response = await fetch('/criar-pedido', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(pedidoData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showStatus(`✅ Pedido ${result.numero_pedido} criado com sucesso!`, 'success');
                    document.getElementById('orderForm').reset();
                    document.getElementById('totalPedido').textContent = '0.00';
                    
                    // Reset itens
                    const container = document.getElementById('itensContainer');
                    container.innerHTML = container.firstElementChild.outerHTML;
                    updateProdutoSelects();
                    setupItemEvents(container.firstElementChild);
                    
                } else {
                    showStatus(`❌ Erro: ${result.erro}`, 'error');
                }
                
            } catch (error) {
                console.error('Erro ao criar pedido:', error);
                showStatus('❌ Erro ao conectar com servidor', 'error');
            }
        });
        
        // Setup initial events
        document.addEventListener('DOMContentLoaded', function() {
            loadInitialData();
            setupItemEvents(document.querySelector('.item-row'));
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
                'database': 'PostgreSQL - Conectado (Railway)',
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


@app.route('/criar-pedido', methods=['POST'])
def criar_pedido():
    """Endpoint para criar pedido"""
    try:
        dados = request.get_json()
        resultado = salvar_pedido(dados)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({
            'success': False,
            'erro': f'Erro interno: {str(e)}'
        }), 500


if __name__ == '__main__':
    # Obter porta do ambiente (Railway define automaticamente)
    port = int(os.environ.get('PORT', 5001))

    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Railway Deploy")
        print(f"📡 Servidor rodando na porta: {port}")
        print("🔗 Endpoints disponíveis:")
        print("   • /health - Status do sistema")
        print("   • /clientes - Lista de clientes")
        print("   • /precos - Tabela de preços")
        print("   • /pedidos - Criar pedidos")
        print("-" * 50)

        # Para Railway: usar host='0.0.0.0' e port do ambiente
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("❌ Falha na inicialização do banco de dados")
        sys.exit(1)
