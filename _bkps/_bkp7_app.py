from flask import Flask, render_template, request, jsonify, send_file
from flask import send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json
import socket
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from decouple import config
import sys
import locale
import psycopg2
from flask import Flask, render_template_string, request, jsonify, send_file
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'designtex-vendas-postgresql-2024'
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

# CONFIGURAÇÃO DO POSTGRESQL
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'designtex_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'samuca88'),
    'port': os.getenv('DB_PORT', '5432'),
    'client_encoding': 'UTF8',  # ← ADICIONAR ESTA LINHA
    'connect_timeout': 30       # ← E ESTA TAMBÉM
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


# CONFIGURAÇÕES DE EMAIL
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'email': os.getenv('EMAIL_USER', 'design.designtextecidos@gmail.com'),
    'password': os.getenv('EMAIL_PASS', 'kmqq xayd plif mrgb'),
    'destinatario': 'pedido@designtextecidos.com.br'
}


def get_db_connection():
    """Conectar ao PostgreSQL"""
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar PostgreSQL: {e}")
        return None


def init_database():
    """Inicializar todas as tabelas do PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # 1. TABELA DE CLIENTES
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                cnpj VARCHAR(20) UNIQUE NOT NULL,
                razao_social VARCHAR(200) NOT NULL,
                nome_fantasia VARCHAR(200),
                telefone VARCHAR(20),
                email VARCHAR(100),
                endereco TEXT,
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. TABELA DE PREÇOS NORMAL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS precos_normal (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50) NOT NULL,
                codigo VARCHAR(50) NOT NULL,
                descricao VARCHAR(200),
                icms_18 DECIMAL(10,2),
                icms_12 DECIMAL(10,2),
                icms_7 DECIMAL(10,2),
                ret_mg DECIMAL(10,2),
                ativo BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 3. TABELA DE PREÇOS LD
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS precos_ld (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50) NOT NULL,
                codigo VARCHAR(50) NOT NULL,
                descricao VARCHAR(200),
                icms_18_ld DECIMAL(10,2),
                icms_12_ld DECIMAL(10,2),
                icms_7_ld DECIMAL(10,2),
                ret_ld_mg DECIMAL(10,2),
                ativo BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 4. TABELA DE PEDIDOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(20) UNIQUE NOT NULL,
                representante VARCHAR(100) NOT NULL,
                cliente_cnpj VARCHAR(20) NOT NULL,
                dados_pedido JSONB NOT NULL,
                valor_total DECIMAL(12,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'ENVIADO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 5. TABELA PARA NUMERAÇÃO
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sequencia_pedidos (
                id SERIAL PRIMARY KEY,
                ultimo_numero INTEGER DEFAULT 0
            )
        ''')

        # Inserir registro inicial da sequência se não existir
        cursor.execute('SELECT COUNT(*) FROM sequencia_pedidos')
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                'INSERT INTO sequencia_pedidos (ultimo_numero) VALUES (0)')

        conn.commit()
        print("✅ Tabelas PostgreSQL criadas com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def inserir_clientes_iniciais():
    """Inserir clientes iniciais no PostgreSQL"""
    clientes_iniciais = [
        ("12.345.678/0001-90", "EMPRESA ABC LTDA", "EMPRESA ABC", "11999990001"),
        ("98.765.432/0001-10", "COMERCIAL XYZ S/A", "COMERCIAL XYZ", "11999990002"),
        ("11.222.333/0001-44", "DISTRIBUIDORA 123 LTDA",
         "DISTRIBUIDORA 123", "11999990003"),
        ("55.666.777/0001-88", "CONFECÇÕES DELTA LTDA",
         "CONFECÇÕES DELTA", "11999990004"),
        ("33.444.555/0001-66", "INDÚSTRIA BETA LTDA",
         "INDÚSTRIA BETA", "11999990005"),
        ("77.888.999/0001-22", "TÊXTIL GAMMA S/A", "TÊXTIL GAMMA", "11999990006")
    ]

    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        for cnpj, razao_social, nome_fantasia, telefone in clientes_iniciais:
            cursor.execute('''
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (cnpj) DO NOTHING
            ''', (cnpj, razao_social, nome_fantasia, telefone))

        conn.commit()
        print("✅ Clientes iniciais inseridos!")
        return True

    except Exception as e:
        print(f"❌ Erro ao inserir clientes: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def gerar_numero_pedido():
    """Gerar número sequencial do PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return "0001"

    try:
        cursor = conn.cursor()

        # Incrementar e buscar próximo número
        cursor.execute('''
            UPDATE sequencia_pedidos 
            SET ultimo_numero = ultimo_numero + 1 
            WHERE id = 1 
            RETURNING ultimo_numero
        ''')

        resultado = cursor.fetchone()
        proximo_numero = resultado[0] if resultado else 1

        conn.commit()

        # Formato: 0001, 0002, ..., 9999, 10000, 10001...
        if proximo_numero <= 9999:
            return f"{proximo_numero:04d}"
        else:
            return str(proximo_numero)

    except Exception as e:
        print(f"❌ Erro ao gerar número: {e}")
        return "0001"
    finally:
        cursor.close()
        conn.close()


def salvar_pedido_postgresql(dados_pedido):
    """Salvar pedido no PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO pedidos (numero_pedido, representante, cliente_cnpj, dados_pedido, valor_total)
            VALUES (%s, %s, %s, %s, %s)
        ''', (
            dados_pedido['numero_pedido'],
            dados_pedido['dados_cabecalho']['representante'],
            dados_pedido['dados_cabecalho']['cnpj'],
            json.dumps(dados_pedido),
            dados_pedido['valor_total']
        ))

        conn.commit()
        print(f"✅ Pedido {dados_pedido['numero_pedido']} salvo no PostgreSQL!")
        return True

    except Exception as e:
        print(f"❌ Erro ao salvar pedido: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


@app.route('/api/buscar_clientes')
def buscar_clientes():
    """API para buscar clientes do PostgreSQL"""
    query = request.args.get('q', '').strip().lower()

    if len(query) < 1:
        return jsonify([])

    conn = get_db_connection()
    if not conn:
        return jsonify([])

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute('''
            SELECT cnpj, razao_social, nome_fantasia, telefone 
            FROM clientes 
            WHERE ativo = TRUE 
            AND (
                LOWER(cnpj) LIKE %s OR 
                LOWER(razao_social) LIKE %s OR 
                LOWER(nome_fantasia) LIKE %s OR
                REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '/', ''), '-', '') LIKE %s
            )
            ORDER BY razao_social
            LIMIT 10
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))

        resultados = cursor.fetchall()
        return jsonify([dict(row) for row in resultados])

    except Exception as e:
        print(f"❌ Erro na busca: {e}")
        return jsonify([])
    finally:
        cursor.close()
        conn.close()


@app.route('/')
def index():
    # Buscar todos os clientes do PostgreSQL
    conn = get_db_connection()
    clientes_data = {}
    clientes_nomes = {}

    if conn:
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                'SELECT cnpj, razao_social, nome_fantasia FROM clientes WHERE ativo = TRUE')
            clientes = cursor.fetchall()

            for cliente in clientes:
                clientes_data[cliente['cnpj']] = cliente['razao_social']
                clientes_nomes[cliente['cnpj']] = cliente['nome_fantasia']

        except Exception as e:
            print(f"❌ Erro ao carregar clientes: {e}")
        finally:
            cursor.close()
            conn.close()

    prazos = [
        "À Vista", "7 dias", "14 dias", "21 dias", "28 dias", "56 dias", "84 dias",
        "56/84 dias", "56/84/112 dias", "7/14/21 dias", "21/28/35 dias",
        "35/42/49 dias", "49/56/63 dias", "42/49/56/63/70 dias",
        "56/63/70/77/84 dias", "84/112/140 dias", "56/70/84/98/112 dias"
    ]

    return render_template('index.html',
                           clientes=clientes_data,
                           clientes_nomes=clientes_nomes,
                           prazos=prazos)


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Submissão com PostgreSQL"""
    try:
        data = request.get_json()
        print("✅ Pedido recebido para PostgreSQL")

        # Validações (mantém as mesmas do código anterior)
        required_fields = {
            'nomeRepresentante': 'Nome do representante',
            'razaoSocial': 'Razão Social',
            'cnpj': 'CNPJ',
            'telefone': 'Telefone',
            'prazoPagamento': 'Prazo de pagamento',
            'tipoPedido': 'Tipo de pedido',
            'tipoFrete': 'Tipo de frete',
            'tipoProduto': 'Tipo de produto',
            'tabelaPrecos': 'Tabela de Preços'
        }

        for field, label in required_fields.items():
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{label} é obrigatório'})

        if data.get('tipoPedido') == 'OP' and not data.get('numeroOP'):
            return jsonify({'success': False, 'message': 'Número da OP é obrigatório'})

        produtos = data.get('produtos', [])
        if not produtos:
            return jsonify({'success': False, 'message': 'Adicione pelo menos um produto'})

        # Gerar número do pedido
        numero_pedido = gerar_numero_pedido()

        # Dados completos do pedido
        pedido_completo = {
            'numero_pedido': numero_pedido,
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'empresa': 'Designtex Tecidos',
            'dados_cabecalho': {
                'representante': data.get('nomeRepresentante'),
                'razao_social': data.get('razaoSocial'),
                'cnpj': data.get('cnpj'),
                'telefone': data.get('telefone', '')
            },
            'dados_corpo': {
                'prazo_pagamento': data.get('prazoPagamento'),
                'tipo_pedido': data.get('tipoPedido'),
                'numero_op': data.get('numeroOP', ''),
                'tipo_frete': data.get('tipoFrete'),
                'transportadora_fob': data.get('transportadoraFOB', ''),
                'transportadora_cif': data.get('transportadoraCIF', ''),
                'venda_triangular': data.get('vendaTriangular', 'Não'),
                'dados_triangulacao': data.get('dadosTriangulacao', ''),
                'regime_ret': data.get('regimeRET', 'Não'),
                'tipo_produto': data.get('tipoProduto')
            },
            'tabela_precos': {
                'tipo_tabela': data.get('tabelaPrecos')
            },
            'produtos': data.get('produtos', []),
            'valor_total': float(data.get('valorTotal', 0)),
            'observacoes': data.get('observacoes', ''),
        }

        # Salvar no PostgreSQL
        salvar_pedido_postgresql(pedido_completo)

        # Gerar PDF
        pdf_filename = f'pedido_{numero_pedido}.pdf'
        pdf_path = os.path.join('uploads', pdf_filename)
        gerar_pdf_pedido(pedido_completo, pdf_path)

        # Enviar email (mantém a mesma função)
        email_enviado = enviar_email_pedido(pedido_completo, pdf_path)

        return jsonify({
            'success': True,
            'message': f'Pedido {numero_pedido} enviado e salvo no PostgreSQL!',
            'numero_pedido': numero_pedido,
            'timestamp': pedido_completo['timestamp'],
            'pdf': pdf_filename,
            'pdf_url': f'/download_pdf/{pdf_filename}',
            'valor_total': pedido_completo['valor_total'],
            'email_enviado': email_enviado
        })

    except Exception as e:
        print(f"❌ Erro ao processar pedido: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

# Manter as outras funções (gerar_pdf_pedido, download_pdf, etc.)
# ... (código igual ao anterior, só mudando a numeração)


@app.route('/health')
def health_check():
    """Health check com status PostgreSQL"""
    db_status = "Conectado" if get_db_connection() else "Erro"

    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        'empresa': 'Designtex Tecidos',
        'versao': '3.0 - PostgreSQL + Web Deploy',
        'database': f'PostgreSQL - {db_status}',
        'recursos': [
            'PostgreSQL 18 integrado',
            'Clientes em banco de dados',
            'Tabelas de preços Normal e LD',
            'Deploy web pronto',
            'Numeração sequencial simples'
        ]
    })


if __name__ == '__main__':
    # Inicializar PostgreSQL
    print("🔄 Inicializando PostgreSQL...")
    if init_database():
        inserir_clientes_iniciais()

    # Criar pasta uploads
    os.makedirs('uploads', exist_ok=True)

    port = int(os.environ.get('PORT', 5001))

    print("🚀 Iniciando DESIGNTEX TECIDOS - PostgreSQL Web")
    print("=" * 70)
    print("🗄️  Database: PostgreSQL 18")
    print("🌐 Deploy: Pronto para Railway/Render")
    print("🔢 Numeração: 0001, 0002, 9999, 10000...")
    print("📊 Tabelas: Clientes, Preços Normal, Preços LD")
    print("=" * 70)

    app.run(debug=False, host='0.0.0.0', port=port)
