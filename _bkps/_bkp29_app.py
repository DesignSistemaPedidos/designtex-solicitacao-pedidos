import os
import sys
import locale
import psycopg2
from flask import Flask, render_template_string, request, jsonify, send_file
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
import tempfile
import smtplib

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
except ImportError:
    print("⚠️  ReportLab não instalado - PDFs desabilitados")

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
            print(f"✅ Banco já inicializado com {len(tabelas_existentes)} tabelas")
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

        # Tabela pedidos - ATUALIZADA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                razao_social_cliente VARCHAR(200),
                nome_representante VARCHAR(100),
                prazo_pagamento VARCHAR(50),
                tipo_pedido VARCHAR(10),
                numero_op VARCHAR(50),
                tipo_frete VARCHAR(10),
                transportadora VARCHAR(200),
                venda_triangular VARCHAR(10),
                dados_triangulacao TEXT,
                regime_ret VARCHAR(10),
                tipo_produto VARCHAR(20),
                tabela_precos VARCHAR(50),
                observacoes TEXT,
                valor_total DECIMAL(12,2),
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
                subtotal DECIMAL(12,2),
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
            ('98.765.432/0001-10', 'COMERCIAL XYZ SA', 'COMERCIAL XYZ', '11999990002'),
            ('11.222.333/0001-44', 'DISTRIBUIDORA 123 LTDA', 'DISTRIBUIDORA 123', '11999990003'),
            ('22.333.444/0001-55', 'TEXTIL MODELO LTDA', 'TEXTIL MODELO', '11999990004'),
            ('33.444.555/0001-66', 'INDUSTRIA TECIDOS SA', 'INDUSTRIA TECIDOS', '11999990005')
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
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1', 12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D', 15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 40/1', 'VIS401', 'Tecido viscose 40/1', 18.90, 17.80, 16.90, 16.20),
            ('LINHO MISTO', 'LIN001', 'Tecido linho misto', 22.40, 21.30, 20.50, 19.80)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        # Preços LD
        precos_ld = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 LD', 11.50, 10.80, 10.20, 9.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D LD', 14.30, 13.60, 12.90, 12.50)
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
        cursor.execute("UPDATE sequencia_pedidos SET ultimo_numero = ultimo_numero + 1 WHERE id = 1 RETURNING ultimo_numero")
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
        cursor.execute("SELECT cnpj, razao_social, nome_fantasia, telefone FROM clientes ORDER BY razao_social")
        clientes = cursor.fetchall()
        cursor.close()
        conn.close()
        return clientes
    except Exception as e:
        print(f"Erro ao buscar clientes: {e}")
        if conn:
            conn.close()
        return []

def buscar_clientes_por_nome(query):
    """Buscar clientes por nome/razão social"""
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
            ORDER BY razao_social
            LIMIT 10
        """, (f'%{query}%', f'%{query}%'))
        clientes = cursor.fetchall()
        cursor.close()
        conn.close()
        return clientes
    except Exception as e:
        print(f"Erro ao buscar clientes por nome: {e}")
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
    """Salvar pedido no banco de dados"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Obter próximo número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return None

        # Inserir pedido principal
        cursor.execute("""
            INSERT INTO pedidos (
                numero_pedido, cnpj_cliente, razao_social_cliente, nome_representante,
                prazo_pagamento, tipo_pedido, numero_op, tipo_frete, transportadora,
                venda_triangular, dados_triangulacao, regime_ret, tipo_produto,
                tabela_precos, observacoes, valor_total
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero_pedido,
            dados_pedido['cnpj'],
            dados_pedido['razaoSocial'],
            dados_pedido['nomeRepresentante'],
            dados_pedido['prazoPagamento'],
            dados_pedido['tipoPedido'],
            dados_pedido.get('numeroOP', ''),
            dados_pedido['tipoFrete'],
            dados_pedido.get('transportadoraFOB', '') or dados_pedido.get('transportadoraCIF', ''),
            dados_pedido['vendaTriangular'],
            dados_pedido.get('dadosTriangulacao', ''),
            dados_pedido['regimeRET'],
            dados_pedido['tipoProduto'],
            dados_pedido['tabelaPrecos'],
            dados_pedido['observacoes'],
            dados_pedido['valorTotal']
        ))

        # Inserir itens do pedido
        for produto in dados_pedido['produtos']:
            cursor.execute("""
                INSERT INTO itens_pedido (
                    numero_pedido, artigo, codigo, desenho_cor, 
                    metragem, preco_metro, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_pedido,
                produto['artigo'],
                produto['codigo'],
                produto['desenho_cor'],
                produto['metragem'],
                produto['preco'],
                produto['subtotal']
            ))

        conn.commit()
        cursor.close()
        conn.close()

        return numero_pedido

    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None

def buscar_pedido_completo(numero_pedido):
    """Buscar pedido completo com itens"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Buscar dados do pedido
        cursor.execute("""
            SELECT numero_pedido, cnpj_cliente, razao_social_cliente, nome_representante,
                   prazo_pagamento, tipo_pedido, numero_op, tipo_frete, transportadora,
                   venda_triangular, dados_triangulacao, regime_ret, tipo_produto,
                   tabela_precos, observacoes, valor_total, created_at
            FROM pedidos WHERE numero_pedido = %s
        """, (numero_pedido,))

        pedido = cursor.fetchone()
        if not pedido:
            return None

        # Buscar itens do pedido
        cursor.execute("""
            SELECT artigo, codigo, desenho_cor, metragem, preco_metro, subtotal
            FROM itens_pedido WHERE numero_pedido = %s
            ORDER BY id
        """, (numero_pedido,))

        itens = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            'pedido': pedido,
            'itens': itens
        }

    except Exception as e:
        print(f"Erro ao buscar pedido: {e}")
        if conn:
            conn.close()
        return None

def gerar_pdf_pedido(numero_pedido):
    """Gerar PDF do pedido"""

    dados_completos = buscar_pedido_completo(numero_pedido)
    if not dados_completos:
        return None

    pedido = dados_completos['pedido']
    itens = dados_completos['itens']

    # Criar arquivo temporário
    buffer = io.BytesIO()

    try:
        # Configurar documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            alignment=TA_LEFT,
            spaceAfter=10
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT
        )

        # Conteúdo do documento
        story = []

        # Título
        story.append(Paragraph("PEDIDO DE VENDAS - DESIGNTEX TECIDOS", title_style))
        story.append(Spacer(1, 10*mm))

        # Informações do pedido
        story.append(Paragraph("DADOS DO PEDIDO", heading_style))

        info_pedido = [
            ['Número do Pedido:', numero_pedido],
            ['Data:', pedido[16].strftime('%d/%m/%Y %H:%M') if pedido[16] else ''],
            ['Representante:', pedido[3]],
            ['Cliente:', pedido[2]],
            ['CNPJ:', pedido[1]],
            ['Tipo de Pedido:', pedido[5]],
            ['Número OP:', pedido[6] or 'N/A'],
            ['Prazo de Pagamento:', pedido[4]],
            ['Tipo de Frete:', pedido[7]],
            ['Transportadora:', pedido[8] or 'N/A'],
            ['Tabela de Preços:', pedido[13]],
            ['Tipo de Produto:', pedido[12]],
            ['Venda Triangular:', pedido[9]],
            ['Regime RET:', pedido[11]]
        ]

        table_info = Table(info_pedido, colWidths=[50*mm, 120*mm])
        table_info.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        story.append(table_info)
        story.append(Spacer(1, 10*mm))

        # Itens do pedido
        story.append(Paragraph("ITENS DO PEDIDO", heading_style))

        # Cabeçalho da tabela de itens
        data_itens = [
            ['Artigo', 'Código', 'Desenho/Cor', 'Metragem', 'Preço/M', 'Subtotal']
        ]

        # Adicionar itens
        for item in itens:
            data_itens.append([
                item[0],  # artigo
                item[1],  # codigo
                item[2],  # desenho_cor
                f"{item[3]:.2f}m" if item[3] else '0,00m',  # metragem
                f"R$ {item[4]:.2f}" if item[4] else 'R$ 0,00',  # preco_metro
                f"R$ {item[5]:.2f}" if item[5] else 'R$ 0,00'   # subtotal
            ])

        table_itens = Table(data_itens, colWidths=[35*mm, 25*mm, 35*mm, 25*mm, 25*mm, 25*mm])
        table_itens.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table_itens)
        story.append(Spacer(1, 10*mm))

        # Total
        story.append(Paragraph(f"<b>VALOR TOTAL: R$ {pedido[15]:.2f}</b>",
                              ParagraphStyle('Total', parent=styles['Normal'], fontSize=14, alignment=TA_RIGHT)))

        # Observações
        if pedido[14]:  # observacoes
            story.append(Spacer(1, 10*mm))
            story.append(Paragraph("OBSERVAÇÕES", heading_style))
            story.append(Paragraph(pedido[14], normal_style))

        # Triangulação
        if pedido[10]:  # dados_triangulacao
            story.append(Spacer(1, 5*mm))
            story.append(Paragraph("DADOS DA TRIANGULAÇÃO", heading_style))
            story.append(Paragraph(pedido[10], normal_style))

        # Construir documento
        doc.build(story)

        # Retornar PDF como bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return None

# FLASK APP
app = Flask(__name__)

# ROTAS PRINCIPAIS
@app.route('/')
def home():
    """Página inicial com interface moderna"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DESIGNTEX TECIDOS - Sistema de Pedidos</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2563eb;
            --primary-dark: #1d4ed8;
            --secondary-color: #64748b;
            --success-color: #059669;
            --warning-color: #d97706;
            --danger-color: #dc2626;
            --background-color: #f8fafc;
            --card-background: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border-color: #e2e8f0;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        /* HEADER */
        .header {
            background: var(--card-background);
            border-radius: 1rem;
            padding: 2rem;
            box-shadow: var(--shadow-lg);
            text-align: center;
            border: 1px solid var(--border-color);
        }

        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .header .subtitle {
            font-size: 1.125rem;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: #dcfce7;
            color: var(--success-color);
            padding: 0.75rem 1.5rem;
            border-radius: 0.75rem;
            font-weight: 600;
            margin: 1.5rem 0;
            font-size: 0.875rem;
            border: 1px solid #bbf7d0;
        }

        /* GRID LAYOUT */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            flex: 1;
        }

        .card {
            background: var(--card-background);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: var(--shadow-lg);
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-xl);
        }

        .card-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }

        .card-header i {
            width: 2.5rem;
            height: 2.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--primary-color);
            color: white;
            border-radius: 0.75rem;
            font-size: 1.125rem;
        }

        .card-header h3 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        /* BUTTONS */
        .btn-group {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.75rem;
            font-weight: 600;
            font-size: 0.875rem;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            min-height: 2.75rem;
        }

        .btn-primary {
            background: var(--primary-color);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: var(--background-color);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }

        .btn-secondary:hover {
            background: #f1f5f9;
            border-color: var(--secondary-color);
        }

        .btn-success {
            background: var(--success-color);
            color: white;
        }

        .btn-success:hover {
            background: #047857;
            transform: translateY(-1px);
        }

        /* ENDPOINTS LIST */
        .endpoints-list {
            list-style: none;
            margin: 0;
            padding: 0;
        }

        .endpoints-list li {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.2s ease;
        }

        .endpoints-list li:last-child {
            border-bottom: none;
        }

        .endpoints-list li:hover {
            background: var(--background-color);
        }

        .endpoint-method {
            background: var(--success-color);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            font-weight: 600;
            min-width: 3rem;
            text-align: center;
        }

        .endpoint-method.post {
            background: var(--warning-color);
        }

        .endpoint-path {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.875rem;
            color: var(--text-primary);
            font-weight: 500;
        }

        .endpoint-desc {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }

        /* INFO SECTIONS */
        .info-section {
            background: #f8fafc;
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1rem;
            margin-top: 1rem;
        }

        .info-section h4 {
            color: var(--primary-color);
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }

        .info-section p {
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }

        .code-block {
            background: var(--text-primary);
            color: #e2e8f0;
            padding: 0.75rem;
            border-radius: 0.5rem;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.8125rem;
            margin-top: 0.5rem;
            border: 1px solid #334155;
            overflow-x: auto;
        }

        /* STATS GRID */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .stat-item {
            background: var(--background-color);
            padding: 1rem;
            border-radius: 0.75rem;
            text-align: center;
            border: 1px solid var(--border-color);
        }

        .stat-number {
            display: block;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 0.25rem;
        }

        .stat-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* RESPONSIVE */
        @media (max-width: 768px) {
            .main-grid {
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }

            .container {
                padding: 1rem;
                gap: 1.5rem;
            }

            .header {
                padding: 1.5rem;
            }

            .header h1 {
                font-size: 2rem;
                flex-direction: column;
                gap: 0.5rem;
            }

            .card {
                padding: 1.25rem;
            }

            .endpoints-list li {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
            }
        }

        /* ANIMATIONS */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .card, .header {
            animation: fadeInUp 0.6s ease forwards;
        }

        .card:nth-child(2) {
            animation-delay: 0.1s;
        }

        .card:nth-child(3) {
            animation-delay: 0.2s;
        }

        .card:nth-child(4) {
            animation-delay: 0.3s;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <div class="header">
            <h1>
                <i class="fas fa-industry"></i>
                DESIGNTEX TECIDOS
            </h1>
            <p class="subtitle">Sistema de Pedidos de Vendas - PostgreSQL</p>
            
            <div class="status-badge">
                <i class="fas fa-check-circle"></i>
                PostgreSQL Railway Conectado e Funcionando
            </div>

            <div class="stats-grid">
                <div class="stat-item">
                    <span class="stat-number" id="clientesCount">5</span>
                    <span class="stat-label">Clientes</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number" id="precosCount">4</span>
                    <span class="stat-label">Produtos</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number" id="pedidosCount">0</span>
                    <span class="stat-label">Pedidos</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">Online</span>
                    <span class="stat-label">Status</span>
                </div>
            </div>
        </div>

        <!-- MAIN GRID -->
        <div class="main-grid">
            <!-- NAVEGAÇÃO RÁPIDA -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-tachometer-alt"></i>
                    <h3>Navegação Rápida</h3>
                </div>
                
                <div class="btn-group">
                    <a href="/health" class="btn btn-primary" target="_blank">
                        <i class="fas fa-heartbeat"></i>
                        Health Check System
                    </a>
                    
                    <a href="/clientes" class="btn btn-secondary" target="_blank">
                        <i class="fas fa-users"></i>
                        Ver Lista de Clientes
                    </a>
                    
                    <a href="/precos" class="btn btn-secondary" target="_blank">
                        <i class="fas fa-tags"></i>
                        Consultar Preços
                    </a>
                    
                    <button class="btn btn-success" onclick="alert('Em desenvolvimento!')">
                        <i class="fas fa-plus-circle"></i>
                        Criar Novo Pedido
                    </button>
                </div>

                <div class="info-section">
                    <h4>Acesso Local</h4>
                    <p>Sua aplicação está rodando em:</p>
                    <div class="code-block">http://127.0.0.1:5001</div>
                </div>
            </div>

            <!-- API ENDPOINTS -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-code"></i>
                    <h3>API Endpoints</h3>
                </div>

                <ul class="endpoints-list">
                    <li>
                        <div>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/health</span>
                        </div>
                        <span class="endpoint-desc">Status do sistema</span>
                    </li>
                    
                    <li>
                        <div>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/clientes</span>
                        </div>
                        <span class="endpoint-desc">Lista de clientes</span>
                    </li>
                    
                    <li>
                        <div>
                            <span class="endpoint-method">GET</span>
                            <span class="endpoint-path">/precos</span>
                        </div>
                        <span class="endpoint-desc">Tabela de preços</span>
                    </li>
                    
                    <li>
                        <div>
                            <span class="endpoint-method post">POST</span>
                            <span class="endpoint-path">/submit_pedido</span>
                        </div>
                        <span class="endpoint-desc">Criar pedido</span>
                    </li>
                </ul>
            </div>

            <!-- POWER BI INTEGRATION -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-chart-line"></i>
                    <h3>Power BI Integration</h3>
                </div>

                <p style="margin-bottom: 1rem; color: var(--text-secondary);">
                    Configure o Power BI para conectar com esta API.
                </p>

                <div class="info-section">
                    <h4>URL para Power BI</h4>
                    <div class="code-block">http://127.0.0.1:5001</div>
                </div>
            </div>

            <!-- INFORMAÇÕES DO SISTEMA -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-info-circle"></i>
                    <h3>Sistema</h3>
                </div>

                <div class="info-section">
                    <h4>Banco de Dados</h4>
                    <p>PostgreSQL Railway (Cloud)</p>
                </div>

                <div class="info-section">
                    <h4>Framework</h4>
                    <p>Flask Python API</p>
                </div>
            </div>
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

# APIS PARA CLIENTES
@app.route('/clientes')
def listar_clientes():
    """Listar clientes em JSON"""
    clientes = buscar_clientes()
    clientes_json = []

    for cliente in clientes:
        clientes_json.append({
            'cnpj': cliente[0],
            'razao_social': cliente[1],
            'nome_fantasia': cliente[2],
            'telefone': cliente[3] if len(cliente) > 3 else ''
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

@app.route('/api/buscar_clientes')
def api_buscar_clientes():
    """API para buscar clientes por nome"""
    query = request.args.get('q', '').strip()

    if len(query) < 1:
        return jsonify([])

    clientes = buscar_clientes_por_nome(query)
    clientes_json = []

    for cliente in clientes:
        clientes_json.append({
            'cnpj': cliente[0],
            'razao_social': cliente[1],
            'nome_fantasia': cliente[2],
            'telefone': cliente[3] if len(cliente) > 3 else ''
        })

    return jsonify(clientes_json)

# API PARA PEDIDOS
@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Submeter novo pedido"""

    try:
        dados = request.get_json()

        if not dados:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        # Validar dados básicos
        campos_obrigatorios = ['nomeRepresentante', 'razaoSocial', 'cnpj', 'produtos']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                return jsonify({'success': False, 'message': f'Campo obrigatório: {campo}'}), 400

        # Validar se tem produtos
        if not dados.get('produtos') or len(dados['produtos']) == 0:
            return jsonify({'success': False, 'message': 'Pedido deve ter pelo menos um produto'}), 400

        # Salvar pedido no banco
        numero_pedido = salvar_pedido(dados)

        if not numero_pedido:
            return jsonify({'success': False, 'message': 'Erro ao salvar pedido no banco'}), 500

        return jsonify({
            'success': True,
            'message': 'Pedido salvo com sucesso!',
            'numero_pedido': numero_pedido,
            'redirect_url': f'/gerar-pdf/{numero_pedido}'
        })

    except Exception as e:
        print(f"Erro ao processar pedido: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

@app.route('/gerar-pdf/<numero_pedido>')
def gerar_pdf_endpoint(numero_pedido):
    """Gerar e retornar PDF do pedido"""
    
    try:
        pdf_bytes = gerar_pdf_pedido(numero_pedido)
        
        if not pdf_bytes:
            return jsonify({'error': 'Pedido não encontrado ou erro ao gerar PDF'}), 404
        
        # Criar resposta com PDF
        response = send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Pedido_{numero_pedido}.pdf'
        )
        
        return response
        
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return jsonify({'error': f'Erro ao gerar PDF: {str(e)}'}), 500

if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - PostgreSQL Web")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/precos")
        print("-" * 50)
        
        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
