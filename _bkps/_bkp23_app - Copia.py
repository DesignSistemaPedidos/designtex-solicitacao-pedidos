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

# CONFIGURAR ENCODING DO SISTEMA ANTES DE TUDO


def configurar_encoding():
    """Configurar encoding do sistema"""
    try:
        # Windows
        if sys.platform.startswith('win'):
            os.system('chcp 65001 > nul')

        # Configurar variáveis de ambiente
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PGCLIENTENCODING'] = 'SQL_ASCII'  # Mais compatível

        # Configurar locale
        try:
            locale.setlocale(locale.LC_ALL, 'C')  # Mais seguro
        except:
            pass

        print("✅ Encoding configurado com sucesso")

    except Exception as e:
        print(f"⚠️  Aviso na configuração de encoding: {e}")


# Executar configuração de encoding
configurar_encoding()

# CONFIGURAÇÃO DO POSTGRESQL - CORRIGIDA
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'designtex_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'samuca88'),
    'port': os.getenv('DB_PORT', '5432'),
    'client_encoding': 'UTF8',
    'connect_timeout': 30
}


def conectar_postgresql():
    """Conectar ao PostgreSQL com tratamento robusto de encoding"""

    # Lista de encodings para tentar
    encodings_para_testar = ['UTF8', 'LATIN1', 'WIN1252', 'SQL_ASCII']

    for encoding in encodings_para_testar:
        try:
            print(f"🔄 Tentando conectar com encoding: {encoding}")

            # Configuração com encoding específico
            config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'database': os.getenv('DB_NAME', 'designtex_db'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'samuca88'),
                'port': os.getenv('DB_PORT', '5432'),
                'client_encoding': encoding,
                'connect_timeout': 30
            }

            # Tentar conectar
            conn = psycopg2.connect(**config)

            # Configurar encoding após conexão
            conn.set_client_encoding(encoding)

            # Testar conexão com query simples
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
                print(f"❌ Erro de conexão (não é encoding): {error_msg}")
                return None

        except Exception as e:
            print(f"❌ Erro geral com encoding {encoding}: {str(e)[:100]}...")
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

            # Verificar e corrigir estrutura das tabelas
            verificar_e_corrigir_estrutura_tabelas(cursor, conn)

            cursor.close()
            conn.close()
            return True

        # Criar tabelas com estrutura completa
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

        # Tabela pedidos - ESTRUTURA COMPLETA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                representante VARCHAR(100),
                observacoes TEXT,
                valor_total DECIMAL(10,2),
                status VARCHAR(20) DEFAULT 'ATIVO',
                items TEXT,
                data_entrega DATE,
                desconto DECIMAL(5,2) DEFAULT 0,
                frete DECIMAL(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela itens do pedido
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedido_items (
                id SERIAL PRIMARY KEY,
                pedido_id INTEGER REFERENCES pedidos(id) ON DELETE CASCADE,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                quantidade DECIMAL(10,2),
                preco_unitario DECIMAL(10,2),
                total_item DECIMAL(10,2),
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


def verificar_e_corrigir_estrutura_tabelas(cursor, conn):
    """Verificar e corrigir estrutura das tabelas existentes"""

    try:
        # Verificar se coluna status existe na tabela pedidos
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'pedidos' AND column_name = 'status'
        """)
        tem_status = cursor.fetchone()[0] > 0

        if not tem_status:
            print("➕ Adicionando coluna 'status' na tabela pedidos")
            cursor.execute("""
                ALTER TABLE pedidos 
                ADD COLUMN status VARCHAR(20) DEFAULT 'ATIVO'
            """)

        # Verificar outras colunas necessárias
        colunas_necessarias = [
            ('items', 'TEXT'),
            ('data_entrega', 'DATE'),
            ('desconto', 'DECIMAL(5,2) DEFAULT 0'),
            ('frete', 'DECIMAL(10,2) DEFAULT 0')
        ]

        for nome_coluna, tipo_coluna in colunas_necessarias:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'pedidos' AND column_name = %s
            """, (nome_coluna,))

            existe = cursor.fetchone()[0] > 0

            if not existe:
                print(
                    f"➕ Adicionando coluna '{nome_coluna}' na tabela pedidos")
                cursor.execute(f"""
                    ALTER TABLE pedidos 
                    ADD COLUMN {nome_coluna} {tipo_coluna}
                """)

        conn.commit()
        print("✅ Estrutura das tabelas verificada e corrigida")

    except Exception as e:
        print(f"⚠️  Erro ao corrigir estrutura: {e}")
        conn.rollback()


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
            ('22.333.444/0001-55', 'CONFECCOES PAULO LTDA',
             'CONFECCOES PAULO', '11999990004'),
            ('33.444.555/0001-66', 'TEXTIL MODERNA SA',
             'TEXTIL MODERNA', '11999990005')
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

        precos_normal = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D microfibra',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 40/1', 'VIS401', 'Tecido viscose 40/1 lisa',
             18.20, 17.40, 16.60, 16.20),
            ('COTTON 24/1', 'COT241', 'Tecido cotton 24/1 cardado',
             14.80, 14.10, 13.40, 13.00),
            ('MODAL 50/1', 'MOD501', 'Tecido modal 50/1 premium',
             22.50, 21.80, 21.10, 20.70)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos_normal:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        # Preços LD
        precos_ld = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 penteado LD',
             13.20, 12.50, 11.90, 11.50),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D microfibra LD',
             16.00, 15.30, 14.60, 14.20),
            ('VISCOSE 40/1', 'VIS401', 'Tecido viscose 40/1 lisa LD',
             19.00, 18.20, 17.40, 17.00),
            ('COTTON 24/1', 'COT241', 'Tecido cotton 24/1 cardado LD',
             15.50, 14.80, 14.10, 13.70),
            ('MODAL 50/1', 'MOD501', 'Tecido modal 50/1 premium LD',
             23.50, 22.80, 22.10, 21.70)
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
        return str(numero).zfill(4)  # Formatar com zeros à esquerda
    except Exception as e:
        print(f"Erro ao obter número do pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None


def buscar_clientes(query=''):
    """Buscar clientes com filtro opcional"""
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
            cursor.execute(
                "SELECT cnpj, razao_social, nome_fantasia, telefone FROM clientes ORDER BY razao_social")

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
    """Salvar pedido no banco de dados"""

    conn = conectar_postgresql()
    if not conn:
        return {'success': False, 'error': 'Erro de conexão com banco'}

    try:
        cursor = conn.cursor()

        # Obter próximo número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return {'success': False, 'error': 'Erro ao gerar número do pedido'}

        # Preparar dados do pedido
        pedido = {
            'numero_pedido': numero_pedido,
            'cnpj_cliente': dados_pedido.get('cnpj_cliente'),
            'representante': dados_pedido.get('representante'),
            'observacoes': dados_pedido.get('observacoes', ''),
            'valor_total': dados_pedido.get('valor_total', 0)
        }

        # Inserir pedido
        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, representante, observacoes, valor_total)
            VALUES (%(numero_pedido)s, %(cnpj_cliente)s, %(representante)s, %(observacoes)s, %(valor_total)s)
            RETURNING id, numero_pedido, created_at
        """, pedido)

        resultado = cursor.fetchone()
        conn.commit()

        pedido_criado = {
            'id': resultado[0],
            'numero_pedido': resultado[1],
            'cnpj_cliente': pedido['cnpj_cliente'],
            'representante': pedido['representante'],
            'observacoes': pedido['observacoes'],
            'valor_total': float(pedido['valor_total']),
            'created_at': resultado[2].isoformat()
        }

        cursor.close()
        conn.close()

        return {'success': True, 'pedido': pedido_criado}

    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': str(e)}


def buscar_pedidos():
    """Buscar todos os pedidos"""
    conn = conectar_postgresql()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.numero_pedido, p.cnpj_cliente, c.razao_social, p.representante, 
                   p.valor_total, p.created_at
            FROM pedidos p
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj
            ORDER BY p.created_at DESC
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


def buscar_pedido_por_numero(numero_pedido):
    """Buscar pedido específico por número"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, c.razao_social, c.nome_fantasia
            FROM pedidos p
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj
            WHERE p.numero_pedido = %s
        """, (numero_pedido,))
        pedido = cursor.fetchone()
        cursor.close()
        conn.close()
        return pedido
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
        <p class="subtitle">Sistema de Pedidos - PostgreSQL Railway</p>
        
        <div class="status">
            ✅ PostgreSQL Railway Conectado e Funcionando
        </div>
        
        <!-- Botões de teste -->
        <a href="/health" class="btn">🔍 Health Check</a>
        <a href="/clientes" class="btn">👥 Ver Clientes</a>
        <a href="/precos" class="btn">💰 Ver Preços</a>
        <a href="/pedidos" class="btn success">📋 Ver Pedidos</a>
        <a href="/teste-pedido" class="btn warning">🧪 Criar Pedido Teste</a>
        
        <div class="info">
            <h3>📋 Endpoints Disponíveis:</h3>
            <ul class="endpoints">
                <li><code>GET /health</code> - Status do sistema</li>
                <li><code>GET /clientes</code> - Lista de clientes</li>
                <li><code>GET /precos</code> - Tabela de preços</li>
                <li><code>GET /pedidos</code> - Lista de pedidos</li>
                <li><code>POST /pedidos</code> - Criar novo pedido</li>
                <li><code>GET /pedidos/{numero}</code> - Obter pedido específico</li>
                <li><code>GET /teste-pedido</code> - Criar pedido de teste</li>
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


# NOVO ENDPOINT - FORMULÁRIO DE PEDIDOS


def criar_tabela_pedidos_completa():
    """Criar/atualizar tabela pedidos com estrutura completa"""

    conn = conectar_postgresql()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Dropar tabela antiga se existir (para recriar com nova estrutura)
        cursor.execute("DROP TABLE IF EXISTS pedidos CASCADE")

        # Criar tabela completa
        cursor.execute("""
            CREATE TABLE pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                
                -- REPRESENTANTE
                nome_representante VARCHAR(100) NOT NULL,
                
                -- CLIENTE
                cnpj_cliente VARCHAR(18) NOT NULL,
                razao_social_cliente VARCHAR(200) NOT NULL,
                telefone_cliente VARCHAR(20),
                
                -- CONDIÇÕES COMERCIAIS
                prazo_pagamento VARCHAR(50),
                tipo_pedido VARCHAR(20) CHECK (tipo_pedido IN ('NORMAL', 'ESPECIAL')),
                numero_op VARCHAR(50),
                
                -- FRETE
                tipo_frete VARCHAR(10) CHECK (tipo_frete IN ('FOB', 'CIF')),
                transportadora_fob VARCHAR(100),
                transportadora_cif VARCHAR(100),
                
                -- VENDA TRIANGULAR
                venda_triangular BOOLEAN DEFAULT FALSE,
                dados_triangulacao TEXT,
                
                -- REGIME E PRODUTO
                regime_ret VARCHAR(20) CHECK (regime_ret IN ('RET', 'NORMAL')),
                tipo_produto VARCHAR(20) CHECK (tipo_produto IN ('NORMAL', 'LD')),
                tabela_precos VARCHAR(10) CHECK (tabela_precos IN ('NORMAL', 'LD')),
                
                -- FINANCEIRO
                valor_total DECIMAL(12,2) DEFAULT 0.00,
                
                -- OBSERVAÇÕES
                observacoes TEXT,
                
                -- CONTROLE
                status VARCHAR(20) DEFAULT 'ATIVO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Criar índices para performance
        cursor.execute(
            "CREATE INDEX idx_pedidos_numero ON pedidos(numero_pedido)")
        cursor.execute(
            "CREATE INDEX idx_pedidos_cnpj ON pedidos(cnpj_cliente)")
        cursor.execute(
            "CREATE INDEX idx_pedidos_representante ON pedidos(nome_representante)")
        cursor.execute("CREATE INDEX idx_pedidos_data ON pedidos(created_at)")

        conn.commit()
        print("✅ Tabela pedidos criada com estrutura completa!")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erro ao criar tabela pedidos: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def inserir_pedido_completo(dados_pedido):
    """Inserir pedido com todos os campos"""

    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Gerar número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return None

        # Inserir pedido
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
            dados_pedido.get('nome_representante'),
            dados_pedido.get('cnpj_cliente'),
            dados_pedido.get('razao_social_cliente'),
            dados_pedido.get('telefone_cliente'),
            dados_pedido.get('prazo_pagamento'),
            dados_pedido.get('tipo_pedido', 'NORMAL'),
            dados_pedido.get('numero_op'),
            dados_pedido.get('tipo_frete'),
            dados_pedido.get('transportadora_fob'),
            dados_pedido.get('transportadora_cif'),
            dados_pedido.get('venda_triangular', False),
            dados_pedido.get('dados_triangulacao'),
            dados_pedido.get('regime_ret'),
            dados_pedido.get('tipo_produto'),
            dados_pedido.get('tabela_precos'),
            dados_pedido.get('valor_total', 0.00),
            dados_pedido.get('observacoes')
        ))

        pedido_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Pedido {numero_pedido} inserido com ID: {pedido_id}")

        return {
            'id': pedido_id,
            'numero_pedido': numero_pedido,
            'status': 'success'
        }

    except Exception as e:
        print(f"❌ Erro ao inserir pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None


@app.route('/pedidos', methods=['POST'])
def criar_pedido():
    """Criar novo pedido via API"""

    try:
        dados = request.get_json()

        # Validações básicas
        campos_obrigatorios = [
            'nome_representante', 'cnpj_cliente', 'razao_social_cliente'
        ]

        for campo in campos_obrigatorios:
            if not dados.get(campo):
                return jsonify({
                    'error': f'Campo obrigatório: {campo}',
                    'status': 'error'
                }), 400

        # Inserir pedido
        resultado = inserir_pedido_completo(dados)

        if resultado:
            return jsonify({
                'message': 'Pedido criado com sucesso',
                'pedido': resultado,
                'status': 'success'
            }), 201
        else:
            return jsonify({
                'error': 'Falha ao criar pedido',
                'status': 'error'
            }), 500

    except Exception as e:
        return jsonify({
            'error': f'Erro interno: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/pedidos', methods=['GET'])
def listar_pedidos():
    """Listar pedidos com paginação"""

    try:
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        conn = conectar_postgresql()
        if not conn:
            return jsonify({'error': 'Erro de conexão'}), 500

        cursor = conn.cursor()

        # Contar total
        cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = 'ATIVO'")
        total = cursor.fetchone()[0]

        # Buscar pedidos com paginação
        offset = (page - 1) * per_page
        cursor.execute("""
            SELECT 
                id, numero_pedido, nome_representante, cnpj_cliente, 
                razao_social_cliente, valor_total, created_at
            FROM pedidos 
            WHERE status = 'ATIVO'
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

        pedidos = cursor.fetchall()

        pedidos_json = []
        for pedido in pedidos:
            pedidos_json.append({
                'id': pedido[0],
                'numero_pedido': pedido[1],
                'representante': pedido[2],
                'cnpj_cliente': pedido[3],
                'razao_social': pedido[4],
                'valor_total': float(pedido[5]) if pedido[5] else 0,
                'created_at': pedido[6].isoformat() if pedido[6] else None
            })

        cursor.close()
        conn.close()

        return jsonify({
            'pedidos': pedidos_json,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/pedidos/<numero_pedido>')
def buscar_pedido(numero_pedido):
    """Buscar pedido específico por número"""

    try:
        conn = conectar_postgresql()
        if not conn:
            return jsonify({'error': 'Erro de conexão'}), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM pedidos 
            WHERE numero_pedido = %s AND status = 'ATIVO'
        """, (numero_pedido,))

        pedido = cursor.fetchone()

        if not pedido:
            return jsonify({'error': 'Pedido não encontrado'}), 404

        # Estruturar dados do pedido
        pedido_json = {
            'id': pedido[0],
            'numero_pedido': pedido[1],
            'representante': pedido[2],
            'cnpj_cliente': pedido[3],
            'razao_social_cliente': pedido[4],
            'telefone_cliente': pedido[5],
            'prazo_pagamento': pedido[6],
            'tipo_pedido': pedido[7],
            'numero_op': pedido[8],
            'tipo_frete': pedido[9],
            'transportadora_fob': pedido[10],
            'transportadora_cif': pedido[11],
            'venda_triangular': pedido[12],
            'dados_triangulacao': pedido[13],
            'regime_ret': pedido[14],
            'tipo_produto': pedido[15],
            'tabela_precos': pedido[16],
            'valor_total': float(pedido[17]) if pedido[17] else 0,
            'observacoes': pedido[18],
            'status': pedido[19],
            'created_at': pedido[20].isoformat() if pedido[20] else None,
            'updated_at': pedido[21].isoformat() if pedido[21] else None
        }

        cursor.close()
        conn.close()

        return jsonify(pedido_json)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/novo-pedido')
def novo_pedido():
    """Página do formulário de pedidos"""

    # Lista de prazos de pagamento
    prazos_pagamento = [
        "À Vista",
        "30 dias",
        "45 dias",
        "60 dias",
        "30/60 dias",
        "30/60/90 dias",
        "Faturamento Quinzenal",
        "Faturamento Mensal"
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
        
        .btn-home {
            background-color: #6c757d;
            border-color: #6c757d;
            color: white;
            text-decoration: none;
            display: inline-block;
            padding: 10px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        
        .btn-home:hover {
            background-color: #5a6268;
            color: white;
            text-decoration: none;
        }
    </style>
</head>

<body>
    <div class="container">
        <a href="/" class="btn-home">← Voltar ao Início</a>
        
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

                        <!-- NOVO: Campo para Número da OP -->
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

            <!-- PARTE 3 - TABELA DE PREÇOS - CORRIGIDA -->
            <div class="card mb-4">
                <div class="card-header" style="background-color: #1a5490; color: white;">
                    <h5 class="mb-0">💰 TABELA DE PREÇOS</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">Selecione a Tabela de Preços *</label>
                        <div class="row">
                            <!-- CORRIGIDO: Agora é uma seleção única -->
                            <div class="col-md-6">
                                <div class="border p-3 rounded">
                                    <h6>ICMS Normal</h6>
                                    <div>
                                        <input type="radio" id="icms18_normal" name="tabelaPrecos" value="ICMS 18%"
                                            required>
                                        <label for="icms18_normal" class="form-check-label me-3">ICMS 18%</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms12_normal" name="tabelaPrecos" value="ICMS 12%"
                                            required>
                                        <label for="icms12_normal" class="form-check-label me-3">ICMS 12%</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms7_normal" name="tabelaPrecos" value="ICMS 7%"
                                            required>
                                        <label for="icms7_normal" class="form-check-label me-3">ICMS 7%</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="ret_normal" name="tabelaPrecos" value="RET (SOMENTE MG)"
                                            required>
                                        <label for="ret_normal" class="form-check-label">RET (SOMENTE MG)</label>
                                    </div>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="border p-3 rounded">
                                    <h6>ICMS LD</h6>
                                    <div>
                                        <input type="radio" id="icms18_ld" name="tabelaPrecos" value="ICMS 18% LD"
                                            required>
                                        <label for="icms18_ld" class="form-check-label me-3">ICMS 18% LD</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms12_ld" name="tabelaPrecos" value="ICMS 12% LD"
                                            required>
                                        <label for="icms12_ld" class="form-check-label me-3">ICMS 12% LD</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="icms7_ld" name="tabelaPrecos" value="ICMS 7% LD"
                                            required>
                                        <label for="icms7_ld" class="form-check-label me-3">ICMS 7% LD</label>
                                    </div>
                                    <div>
                                        <input type="radio" id="ret_ld" name="tabelaPrecos" value="RET LD (SOMENTE MG)"
                                            required>
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

            // Limpar timeout anterior
            clearTimeout(timeoutId);

            if (query.length < 1) {
                dropdown.style.display = 'none';
                limparDadosCliente();
                return;
            }

            // Debounce de 300ms
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

        // ========== CAMPO NÚMERO DA OP ==========
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

        // ========== VALIDAÇÃO DE FORMULÁRIO ==========
        function validarFormulario() {
            // Validar se tem pelo menos um produto
            const produtos = document.querySelectorAll('.produto-item');
            if (produtos.length === 0) {
                alert('Adicione pelo menos um produto!');
                return false;
            }

            // Validar tabela de preços selecionada
            const tabelaPrecos = document.querySelector('input[name="tabelaPrecos"]:checked');
            if (!tabelaPrecos) {
                alert('Selecione uma tabela de preços (ICMS Normal ou ICMS LD)!');
                return false;
            }

            // Validar número da OP se necessário
            const tipoPedido = document.getElementById('tipoPedido').value;
            const numeroOP = document.getElementById('numeroOP').value;
            if (tipoPedido === 'OP' && !numeroOP.trim()) {
                alert('Número da OP é obrigatório para tipo de pedido OP!');
                document.getElementById('numeroOP').focus();
                return false;
            }

            // Validar se todos os campos obrigatórios estão preenchidos
            const camposObrigatorios = document.querySelectorAll('[required]');
            for (let campo of camposObrigatorios) {
                if (!campo.value.trim()) {
                    const label = campo.previousElementSibling?.textContent || 'Campo obrigatório';
                    alert(`Campo obrigatório não preenchido: ${label}`);
                    campo.focus();
                    return false;
                }
            }

            return true;
        }

        // ========== COLETAR DADOS ==========
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

        // ========== ENVIO DO FORMULÁRIO ==========
        document.getElementById('pedidoForm').addEventListener('submit', function (e) {
            e.preventDefault();

            if (!validarFormulario()) {
                return;
            }

            const dados = coletarDados();
            enviarPedido(dados);
        });

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
                        alert(`📄 Número do pedido: ${data.numero_pedido}`);
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
    ''', prazos=prazos_pagamento)

# API ENDPOINT - BUSCAR CLIENTES


@app.route('/api/buscar_clientes')
def api_buscar_clientes():
    """API para buscar clientes (autocomplete)"""
    query = request.args.get('q', '')
    clientes = buscar_clientes(query)
    return jsonify(clientes)

# API ENDPOINT - SUBMIT PEDIDO


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Processar envio de pedido"""
    try:
        dados = request.get_json()

        # Validar dados recebidos
        if not dados:
            return jsonify({'success': False, 'message': 'Dados não recebidos'})

        # Salvar no banco
        numero_pedido = salvar_pedido(dados)

        if numero_pedido:
            return jsonify({
                'success': True,
                'message': f'Pedido criado com sucesso!',
                'numero_pedido': numero_pedido,
                'valor_total': f"R$ {dados['valorTotal']:.2f}".replace('.', ',')
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Erro ao salvar pedido no banco de dados'
            })

    except Exception as e:
        print(f"Erro ao processar pedido: {e}")
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
    """Listar clientes em JSON"""
    clientes = buscar_clientes()
    return jsonify({
        'clientes': clientes,
        'total': len(clientes)
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


@app.route('/pedidos', methods=['GET', 'POST'])
def gerenciar_pedidos():
    """Gerenciar pedidos - listar ou criar"""

    if request.method == 'GET':
        # Listar pedidos
        pedidos = buscar_pedidos()
        pedidos_json = []

        for pedido in pedidos:
            pedidos_json.append({
                'numero_pedido': pedido[0],
                'cnpj_cliente': pedido[1],
                'razao_social': pedido[2] or 'Cliente não encontrado',
                'representante': pedido[3],
                'valor_total': float(pedido[4]) if pedido[4] else 0,
                'data_criacao': pedido[5].isoformat() if pedido[5] else None
            })

        return jsonify({
            'pedidos': pedidos_json,
            'total': len(pedidos_json)
        })

    elif request.method == 'POST':
        # Criar novo pedido
        try:
            dados = request.get_json()

            if not dados:
                return jsonify({'error': 'Dados não fornecidos'}), 400

            # Validações básicas
            campos_obrigatorios = ['cnpj_cliente', 'representante']
            for campo in campos_obrigatorios:
                if campo not in dados or not dados[campo]:
                    return jsonify({'error': f'Campo obrigatório: {campo}'}), 400

            # Salvar pedido
            resultado = salvar_pedido(dados)

            if resultado['success']:
                return jsonify(resultado['pedido']), 201
            else:
                return jsonify({'error': resultado['error']}), 500

        except Exception as e:
            return jsonify({'error': f'Erro ao processar pedido: {str(e)}'}), 500


@app.route('/pedidos/<numero_pedido>')
def obter_pedido(numero_pedido):
    """Obter pedido específico"""
    pedido = buscar_pedido_por_numero(numero_pedido)

    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404

    pedido_json = {
        'id': pedido[0],
        'numero_pedido': pedido[1],
        'cnpj_cliente': pedido[2],
        'representante': pedido[3],
        'observacoes': pedido[4],
        'valor_total': float(pedido[5]) if pedido[5] else 0,
        'created_at': pedido[6].isoformat() if pedido[6] else None,
        'razao_social': pedido[7],
        'nome_fantasia': pedido[8]
    }

    return jsonify(pedido_json)


@app.route('/teste-pedido')
def teste_criar_pedido():
    """Endpoint para testar criação de pedido"""

    dados_teste = {
        'cnpj_cliente': '12.345.678/0001-90',
        'representante': 'REPRESENTANTE TESTE',
        'observacoes': 'Pedido criado via teste do sistema',
        'valor_total': 2500.75
    }

    resultado = salvar_pedido(dados_teste)

    if resultado['success']:
        return jsonify({
            'message': 'Pedido de teste criado com sucesso!',
            'pedido': resultado['pedido']
        })
    else:
        return jsonify({
            'error': 'Erro ao criar pedido de teste',
            'details': resultado['error']
        }), 500

# CONFIGURAÇÃO PARA PRODUÇÃO RAILWAY


def get_port():
    """Obter porta do ambiente (Railway usa PORT)"""
    return int(os.getenv('PORT', 5001))


def is_production():
    """Verificar se está em produção"""
    return os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('ENVIRONMENT') == 'production'


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - PostgreSQL Web")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/precos")
        print("-" * 50)

        # CONFIGURAÇÃO CORRIGIDA PARA WINDOWS
        try:
            # Porta flexível
            port = int(os.environ.get('PORT', 5001))

            # Configurações do Flask para Windows
            app.run(
                host='127.0.0.1',  # Só localhost por enquanto
                port=port,
                debug=False,  # Debug False para evitar problemas
                threaded=True,  # Threading habilitado
                use_reloader=False  # Reloader desabilitado
            )

        except OSError as e:
            if "soquete" in str(e) or "socket" in str(e):
                print("🔄 Tentando porta alternativa...")
                # Tentar porta diferente
                import random
                nova_porta = random.randint(5002, 5010)
                print(f"🔄 Usando porta {nova_porta}")

                app.run(
                    host='127.0.0.1',
                    port=nova_porta,
                    debug=False,
                    threaded=True,
                    use_reloader=False
                )
            else:
                raise e

    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
