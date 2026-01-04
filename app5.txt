import os
import sys
import locale
import psycopg2
from flask import Flask, render_template_string, request, jsonify, send_file, render_template
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io
# IMPORTS PARA EMAIL
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import tempfile
import json


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

# CONFIGURAÇÃO DE EMAIL
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',  # Para Gmail
    'smtp_port': 587,
    # SUBSTITUIR
    'email_usuario': os.getenv('EMAIL_USER', 'design.designtextecidos@gmail.com'),
    # SUBSTITUIR por senha de app
    'email_senha': os.getenv('EMAIL_PASSWORD', 'qnvv pakn hddi jcjq'),
    # SUBSTITUIR
    'email_remetente': os.getenv('EMAIL_FROM', 'design.designtextecidos@gmail.com')
}


def enviar_email_pedido_completo(dados_pedido, numero_pedido, pdf_buffer):
    """Enviar email com PDF do pedido para os destinatários corretos"""

    # CONFIGURAÇÕES DE EMAIL
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USER = 'design.designtextecidos@gmail.com'
    EMAIL_PASS = 'gyeq qadn xmxl tuxp'

    # DESTINATÁRIOS FIXOS
    EMAIL_DESTINOS = [
        'pedido@designtextecidos.com.br',
        'design2@designtextecidos.com.br'
    ]

    try:
        print(f"📧 Preparando email para: {', '.join(EMAIL_DESTINOS)}")

        # Criar mensagem
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ', '.join(EMAIL_DESTINOS)
        msg['Subject'] = f"🏭 NOVO PEDIDO DTX #{numero_pedido} - {dados_pedido.get('razaoSocial', '')[:30]}"

        # Corpo do email em HTML
        corpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="background: #1a5490; color: white; padding: 20px; text-align: center;">
                <h1>🏭 DESIGNTEX TECIDOS</h1>
                <h2>NOVO PEDIDO DE VENDAS</h2>
            </div>
            
            <div style="padding: 20px;">
                <h3 style="color: #1a5490;">📋 DADOS DO PEDIDO</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Número:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">#{numero_pedido}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Representante:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('nomeRepresentante', '')}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Cliente:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('razaoSocial', '')}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">CNPJ:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('cnpj', '')}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Telefone:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('telefone', '')}</td></tr>
                </table>
                
                <h3 style="color: #1a5490;">💰 CONDIÇÕES COMERCIAIS</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Valor Total:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>R$ {dados_pedido.get('valorTotal', 0):.2f}</strong></td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Tabela de Preços:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('tabelaPrecos', '')}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Prazo Pagamento:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('prazoPagamento', '')}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Tipo Pedido:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('tipoPedido', '')}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9; font-weight: bold;">Tipo Frete:</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{dados_pedido.get('tipoFrete', '')}</td></tr>
                </table>
                
                <h3 style="color: #1a5490;">📦 PRODUTOS ({len(dados_pedido.get('produtos', []))} itens)</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr style="background: #1a5490; color: white;">
                        <th style="padding: 10px; text-align: left;">Artigo</th>
                        <th style="padding: 10px; text-align: left;">Código</th>
                        <th style="padding: 10px; text-align: left;">Desenho/Cor</th>
                        <th style="padding: 10px; text-align: center;">Metragem</th>
                        <th style="padding: 10px; text-align: right;">Preço</th>
                        <th style="padding: 10px; text-align: right;">Subtotal</th>
                    </tr>
        """

        # Adicionar produtos na tabela
        for produto in dados_pedido.get('produtos', []):
            corpo_html += f"""
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 8px;">{produto.get('artigo', '')}</td>
                        <td style="padding: 8px;">{produto.get('codigo', '')}</td>
                        <td style="padding: 8px;">{produto.get('desenho_cor', '')}</td>
                        <td style="padding: 8px; text-align: center;">{produto.get('metragem', 0):.2f}m</td>
                        <td style="padding: 8px; text-align: right;">R$ {produto.get('preco', 0):.2f}</td>
                        <td style="padding: 8px; text-align: right;"><strong>R$ {produto.get('subtotal', 0):.2f}</strong></td>
                    </tr>
            """

        corpo_html += f"""
                    <tr style="background: #f0f0f0; font-weight: bold;">
                        <td colspan="5" style="padding: 12px; text-align: right;">TOTAL GERAL:</td>
                        <td style="padding: 12px; text-align: right; color: #1a5490; font-size: 18px;">R$ {dados_pedido.get('valorTotal', 0):.2f}</td>
                    </tr>
                </table>
        """

        # Observações se existirem
        if dados_pedido.get('observacoes'):
            corpo_html += f"""
                <h3 style="color: #1a5490;">📝 OBSERVAÇÕES</h3>
                <div style="background: #f9f9f9; padding: 15px; border-left: 4px solid #1a5490; margin-bottom: 20px;">
                    {dados_pedido.get('observacoes', '').replace('\n', '<br>')}
                </div>
            """

        corpo_html += f"""
                <div style="margin-top: 30px; padding: 15px; background: #f0f8ff; border: 1px solid #1a5490;">
                    <h4 style="color: #1a5490; margin: 0;">📄 DOCUMENTOS</h4>
                    <p style="margin: 5px 0;">✅ PDF do pedido completo em anexo</p>
                    <p style="margin: 5px 0;">🕐 Recebido em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding: 20px; background: #1a5490; color: white;">
                    <p style="margin: 0;"><strong>Sistema de Pedidos DESIGNTEX TECIDOS</strong></p>
                    <p style="margin: 5px 0; font-size: 14px;">Email gerado automaticamente - Não responder</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(corpo_html, 'html'))

        # Anexar PDF
        if pdf_buffer and pdf_buffer.getvalue():
            pdf_buffer.seek(0)
            part = MIMEBase('application', 'pdf')
            part.set_payload(pdf_buffer.read())
            encoders.encode_base64(part)

            # Nome do arquivo PDF
            nome_arquivo = f"Pedido_DTX_{numero_pedido}_{dados_pedido.get('razaoSocial', '').replace(' ', '_').replace('/', '_')[:20]}.pdf"
            part.add_header('Content-Disposition',
                            f'attachment; filename="{nome_arquivo}"')
            msg.attach(part)

            print("✅ PDF anexado ao email")
        else:
            print("⚠️ Nenhum PDF para anexar")

        # Enviar email
        print("📤 Enviando email...")
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)

        text = msg.as_string()
        server.sendmail(EMAIL_USER, EMAIL_DESTINOS, text)
        server.quit()

        print(f"✅ Email enviado com SUCESSO para: {', '.join(EMAIL_DESTINOS)}")
        return True

    except Exception as e:
        print(f"❌ ERRO ao enviar email: {str(e)}")
        import traceback
        print(f"🔍 Detalhes do erro: {traceback.format_exc()}")
        return False


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

        # Tabela pedidos (ATUALIZADA)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                representante VARCHAR(100),
                observacoes TEXT,
                valor_total DECIMAL(10,2),
                tipo_pedido VARCHAR(10),
                numero_op VARCHAR(20),
                tabela_precos VARCHAR(50),
                tipo_produto VARCHAR(50),
                tipo_frete VARCHAR(10),
                venda_triangular VARCHAR(5),
                regime_ret VARCHAR(5),
                dados_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela itens_pedido (NOVA)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id SERIAL PRIMARY KEY,
                pedido_id INTEGER REFERENCES pedidos(id),
                artigo VARCHAR(100),
                codigo VARCHAR(50),
                desenho_cor VARCHAR(100),
                metragem DECIMAL(10,2),
                preco DECIMAL(10,2),
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
            ('22.333.444/0001-55', 'CONFECCOES DELTA LTDA',
             'CONFECCOES DELTA', '11999990004'),
            ('33.444.555/0001-66', 'TEXTIL OMEGA SA', 'TEXTIL OMEGA', '11999990005')
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
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1 - 1,50m',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D - 1,40m',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 30/1', 'VIS301', 'Tecido viscose 30/1 - 1,50m',
             18.90, 17.20, 16.50, 16.00),
            ('MODAL 40/1', 'MOD401', 'Tecido modal 40/1 - 1,60m',
             22.80, 21.90, 21.10, 20.50)
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
            "SELECT cnpj, razao_social, nome_fantasia, telefone FROM clientes ORDER BY razao_social")
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
    """Salvar pedido no banco de dados"""
    conn = conectar_postgresql()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Obter número do pedido
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return None

        # Inserir pedido principal
        cursor.execute("""
            INSERT INTO pedidos (
                numero_pedido, cnpj_cliente, representante, observacoes, 
                valor_total, tipo_pedido, numero_op, tabela_precos, 
                tipo_produto, tipo_frete, venda_triangular, regime_ret,
                dados_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            numero_pedido,
            dados_pedido.get('cnpj'),
            dados_pedido.get('nomeRepresentante'),
            dados_pedido.get('observacoes'),
            dados_pedido.get('valorTotal'),
            dados_pedido.get('tipoPedido'),
            dados_pedido.get('numeroOP'),
            dados_pedido.get('tabelaPrecos'),
            dados_pedido.get('tipoProduto'),
            dados_pedido.get('tipoFrete'),
            dados_pedido.get('vendaTriangular'),
            dados_pedido.get('regimeRET'),
            json.dumps(dados_pedido)  # JSON completo para backup
        ))

        pedido_id = cursor.fetchone()[0]

        # Inserir itens do pedido
        for produto in dados_pedido.get('produtos', []):
            cursor.execute("""
                INSERT INTO itens_pedido (
                    pedido_id, artigo, codigo, desenho_cor, 
                    metragem, preco, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                pedido_id,
                produto.get('artigo'),
                produto.get('codigo'),
                produto.get('desenho_cor'),
                produto.get('metragem'),
                produto.get('preco'),
                produto.get('subtotal')
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


def gerar_pdf_pedido(dados_pedido, numero_pedido):
    """Gerar PDF do pedido"""
    try:
        # Criar buffer em memória
        buffer = io.BytesIO()

        # Criar documento PDF
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=20*mm, leftMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle',
                                     parent=styles['Heading1'],
                                     fontSize=16,
                                     spaceAfter=30,
                                     alignment=1)  # Centralizado

        # Conteúdo do PDF
        story = []

        # Cabeçalho
        story.append(Paragraph("DESIGNTEX TECIDOS", title_style))
        story.append(
            Paragraph(f"PEDIDO DE VENDAS Nº {numero_pedido}", title_style))
        story.append(Spacer(1, 20))

        # Dados do cliente
        cliente_data = [
            ['DADOS DO CLIENTE', ''],
            ['Representante:', dados_pedido.get('nomeRepresentante', '')],
            ['Cliente:', dados_pedido.get('razaoSocial', '')],
            ['CNPJ:', dados_pedido.get('cnpj', '')],
            ['Telefone:', dados_pedido.get('telefone', '')],
        ]

        cliente_table = Table(cliente_data, colWidths=[4*cm, 12*cm])
        cliente_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(cliente_table)
        story.append(Spacer(1, 20))

        # Condições do pedido
        condicoes_data = [
            ['CONDIÇÕES DO PEDIDO', ''],
            ['Tipo Pedido:', dados_pedido.get('tipoPedido', '')],
            ['Número OP:', dados_pedido.get('numeroOP', 'N/A')],
            ['Tabela Preços:', dados_pedido.get('tabelaPrecos', '')],
            ['Tipo Produto:', dados_pedido.get('tipoProduto', '')],
            ['Tipo Frete:', dados_pedido.get('tipoFrete', '')],
            ['Venda Triangular:', dados_pedido.get('vendaTriangular', '')],
            ['Regime RET:', dados_pedido.get('regimeRET', '')],
        ]

        condicoes_table = Table(condicoes_data, colWidths=[4*cm, 12*cm])
        condicoes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(condicoes_table)
        story.append(Spacer(1, 20))

        # Produtos
        produtos_data = [['Artigo', 'Código',
                          'Desenho/Cor', 'Metragem', 'Preço', 'Subtotal']]

        for produto in dados_pedido.get('produtos', []):
            produtos_data.append([
                produto.get('artigo', ''),
                produto.get('codigo', ''),
                produto.get('desenho_cor', ''),
                f"{produto.get('metragem', 0):.2f}",
                f"R$ {produto.get('preco', 0):.2f}",
                f"R$ {produto.get('subtotal', 0):.2f}"
            ])

        # Total
        produtos_data.append(
            ['', '', '', '', 'TOTAL:', f"R$ {dados_pedido.get('valorTotal', 0):.2f}"])

        produtos_table = Table(produtos_data, colWidths=[
                               3*cm, 2*cm, 4*cm, 2*cm, 2.5*cm, 2.5*cm])
        produtos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(produtos_table)
        story.append(Spacer(1, 20))

        # Observações
        if dados_pedido.get('observacoes'):
            story.append(Paragraph("OBSERVAÇÕES:", styles['Heading2']))
            story.append(Paragraph(dados_pedido.get(
                'observacoes'), styles['Normal']))

        # Rodapé
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            f"Pedido gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))

        # Gerar PDF
        doc.build(story)

        # Retornar buffer
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
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
        .btn.primary {
            background: #28a745;
            font-size: 1.2em;
            padding: 15px 40px;
        }
        .btn.primary:hover {
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🏭 DESIGNTEX TECIDOS</h1>
        <p class="subtitle">Sistema de Pedidos - PostgreSQL</p>
        
        <div class="status">
            ✅ Sistema Funcionando - Railway PostgreSQL
        </div>
        
        <a href="/criar-pedido" class="btn primary">📋 CRIAR NOVO PEDIDO</a>
        
        <br><br>
        
        <a href="/health" class="btn">🔍 Health Check</a>
        <a href="/clientes" class="btn">👥 Ver Clientes</a>
        <a href="/precos" class="btn">💰 Ver Preços</a>
        
        <div class="info">
            <h3>📋 Endpoints Disponíveis:</h3>
            <ul class="endpoints">
                <li><code>GET /criar-pedido</code> - Formulário de pedidos</li>
                <li><code>POST /submit_pedido</code> - Enviar pedido</li>
                <li><code>GET /health</code> - Status do sistema</li>
                <li><code>GET /clientes</code> - Lista de clientes</li>
                <li><code>GET /precos</code> - Tabela de preços</li>
                <li><code>GET /api/buscar_clientes</code> - Buscar clientes</li>
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


@app.route('/criar-pedido')
def criar_pedido():
    """Página para criar novo pedido"""

    # Lista de prazos de pagamento
    prazos = [
        "À vista",
        "7 dias",
        "14 dias",
        "21 dias",
        "28 dias",
        "30 dias",
        "45 dias",
        "60 dias"
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
        
        .btn-voltar {
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: inline-block;
        }
        
        .btn-voltar:hover {
            background-color: #5a6268;
            color: white;
            text-decoration: none;
        }
    </style>
</head>

<body>
    <div class="container">
        <a href="/" class="btn-voltar">⬅️ Voltar ao Início</a>
        
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
                                ''' + ''.join([f'<option value="{prazo}">{prazo}</option>' for prazo in prazos]) + '''
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

            <!-- PARTE 3 - TABELA DE PREÇOS -->
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

            produto.querySelector('.subtotal').value = `R$ ${subtotal.toFixed(2)}`;
            calcularTotal();
        }

        function calcularTotal() {
            let total = 0;
            document.querySelectorAll('.subtotal').forEach(input => {
                const valor = parseFloat(input.value.replace('R$ ', '').replace(',', '.')) || 0;
                total += valor;
            });
            document.getElementById('valorTotal').textContent = total.toFixed(2).replace('.', ',');
        }

        // ========== CONTADOR DE CARACTERES ==========
        document.getElementById('observacoes').addEventListener('input', function() {
            const contador = document.getElementById('contadorCaracteres');
            contador.textContent = this.value.length;
        });

        // ========== LIMPAR FORMULÁRIO ==========
        function limparFormulario() {
            if (confirm('Tem certeza que deseja limpar todos os dados do formulário?')) {
                document.getElementById('pedidoForm').reset();
                document.getElementById('produtos-container').innerHTML = '';
                contadorProdutos = 0;
                document.getElementById('valorTotal').textContent = '0,00';
                document.getElementById('contadorCaracteres').textContent = '0';
                
                // Esconder campos condicionais
                document.getElementById('campoNumeroOP').style.display = 'none';
                document.getElementById('campoTransportadoraFOB').style.display = 'none';
                document.getElementById('campoTransportadoraCIF').style.display = 'none';
                document.getElementById('campoTriangulacao').style.display = 'none';
            }
        }

        // ========== ENVIAR FORMULÁRIO ==========
        document.getElementById('pedidoForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Verificar se tem pelo menos um produto
            if (contadorProdutos === 0 || document.querySelectorAll('.produto-item').length === 0) {
                alert('❌ Adicione pelo menos um produto ao pedido!');
                return;
            }
            
            // Coletar dados do formulário
            const dados = coletarDadosFormulario();
            
            if (!dados) {
                return; // Erro na coleta de dados
            }
            
            // Enviar pedido
            enviarPedido(dados);
        });

        function coletarDadosFormulario() {
            try {
                // Dados básicos
                const dados = {
                    nomeRepresentante: document.getElementById('nomeRepresentante').value,
                    razaoSocial: document.getElementById('razaoSocial').value,
                    cnpj: document.getElementById('cnpj').value,
                    telefone: document.getElementById('telefone').value,
                    prazoPagamento: document.getElementById('prazoPagamento').value,
                    tipoPedido: document.getElementById('tipoPedido').value,
                    numeroOP: document.getElementById('numeroOP').value,
                    tipoFrete: document.getElementById('tipoFrete').value,
                    tipoProduto: document.getElementById('tipoProduto').value,
                    vendaTriangular: document.getElementById('vendaTriangular').value,
                    regimeRET: document.getElementById('regimeRET').value,
                    observacoes: document.getElementById('observacoes').value,
                    tabelaPrecos: document.querySelector('input[name="tabelaPrecos"]:checked')?.value || '',
                    produtos: [],
                    valorTotal: parseFloat(document.getElementById('valorTotal').textContent.replace(',', '.'))
                };

                // Coletar produtos
                document.querySelectorAll('.produto-item').forEach(produto => {
                    const artigo = produto.querySelector('input[name="artigo"]').value;
                    const codigo = produto.querySelector('input[name="codigo"]').value;
                    const desenho_cor = produto.querySelector('input[name="desenho_cor"]').value;
                    const metragem = parseFloat(produto.querySelector('input[name="metragem"]').value) || 0;
                    const preco = parseFloat(produto.querySelector('input[name="preco"]').value) || 0;
                    const subtotal = metragem * preco;

                    dados.produtos.push({
                        artigo,
                        codigo,
                        desenho_cor,
                        metragem,
                        preco,
                        subtotal
                    });
                });

                return dados;
                
            } catch (error) {
                console.error('Erro ao coletar dados:', error);
                alert('❌ Erro ao processar dados do formulário!');
                return null;
            }
        }

        function enviarPedido(dados) {
            // Mostrar loading
            const btnEnviar = document.querySelector('button[type="submit"]');
            const textoOriginal = btnEnviar.innerHTML;
            btnEnviar.innerHTML = '⏳ Enviando...';
            btnEnviar.disabled = true;

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
                    alert(`✅ Pedido enviado com sucesso!\\nNúmero: ${data.numero_pedido}\\nPDF enviado por email.`);
                    
                    // Limpar formulário após sucesso
                    limparFormulario();
                } else {
                    alert(`❌ Erro ao enviar pedido: ${data.error}`);
                }
            })
            .catch(error => {
                console.error('Erro:', error);
                alert('❌ Erro de comunicação com o servidor!');
            })
            .finally(() => {
                // Restaurar botão
                btnEnviar.innerHTML = textoOriginal;
                btnEnviar.disabled = false;
            });
        }

        // Adicionar primeiro produto automaticamente quando a página carregar
        document.addEventListener('DOMContentLoaded', function() {
            adicionarProduto();
        });
    </script>
</body>
</html>
    ''')

# ENDPOINTS DA API


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Receber e processar pedido"""
    try:
        dados = request.get_json()

        if not dados:
            return jsonify({'success': False, 'error': 'Dados não recebidos'})

        # Salvar pedido no banco
        numero_pedido = salvar_pedido(dados)

        if not numero_pedido:
            return jsonify({'success': False, 'error': 'Erro ao salvar no banco de dados'})

        # Gerar PDF
        pdf_buffer = gerar_pdf_pedido(dados, numero_pedido)

        if not pdf_buffer:
            return jsonify({'success': False, 'error': 'Erro ao gerar PDF'})

        # Enviar email
        email_sucesso = enviar_email_pedido(dados, numero_pedido, pdf_buffer)

        if not email_sucesso:
            print("⚠️ Pedido salvo mas email não enviado")

        return jsonify({
            'success': True,
            'numero_pedido': numero_pedido,
            'email_enviado': email_sucesso
        })

    except Exception as e:
        print(f"Erro no submit_pedido: {e}")
        return jsonify({'success': False, 'error': str(e)})


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
    """API para buscar clientes (para o autocomplete)"""
    try:
        query = request.args.get('q', '').strip()

        if len(query) < 1:
            return jsonify([])

        conn = conectar_postgresql()
        if not conn:
            return jsonify([]), 500

        cursor = conn.cursor()

        # Buscar clientes que contenham a query na razão social
        cursor.execute("""
            SELECT cnpj, razao_social, nome_fantasia, telefone
            FROM clientes 
            WHERE razao_social ILIKE %s OR nome_fantasia ILIKE %s
            ORDER BY razao_social
            LIMIT 10
        """, (f'%{query}%', f'%{query}%'))

        resultados = cursor.fetchall()
        cursor.close()
        conn.close()

        clientes = []
        for resultado in resultados:
            clientes.append({
                'cnpj': resultado[0],
                'razao_social': resultado[1],
                'nome_fantasia': resultado[2],
                'telefone': resultado[3] or ''
            })

        return jsonify(clientes)

    except Exception as e:
        print(f"Erro na busca de clientes: {e}")
        return jsonify([]), 500


@app.route('/api/buscar_clientes')
def api_buscar_clientes():
    """API para buscar clientes (autocomplete)"""
    try:
        termo = request.args.get('q', '').strip().upper()
        clientes = buscar_clientes()

        if termo:
            clientes_filtrados = []
            for cliente in clientes:
                # Busca em razão social e CNPJ
                if termo in cliente[1].upper() or termo in cliente[0]:
                    clientes_filtrados.append(cliente)
        else:
            clientes_filtrados = clientes[:10]  # Limitar a 10 se não há filtro

        resultado = []
        for cliente in clientes_filtrados:
            resultado.append({
                'cnpj': cliente[0],
                'razaoSocial': cliente[1],
                'nomeFantasia': cliente[2] or '',
                'telefone': cliente[3] or ''
            })

        return jsonify(resultado)

    except Exception as e:
        print(f"Erro na busca de clientes: {e}")
        return jsonify([]), 500


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Processar envio do pedido"""
    try:
        # Receber dados do formulário
        dados = request.json
        print(f"📥 Recebendo pedido: {dados}")

        # Validar dados básicos
        if not dados.get('nomeRepresentante'):
            return jsonify({'success': False, 'error': 'Nome do representante é obrigatório'}), 400

        if not dados.get('cnpj'):
            return jsonify({'success': False, 'error': 'CNPJ do cliente é obrigatório'}), 400

        if not dados.get('produtos') or len(dados.get('produtos', [])) == 0:
            return jsonify({'success': False, 'error': 'Pelo menos um produto deve ser adicionado'}), 400

        # Calcular valor total
        valor_total = 0
        for produto in dados.get('produtos', []):
            metragem = float(produto.get('metragem', 0))
            preco = float(produto.get('preco', 0))
            subtotal = metragem * preco
            produto['subtotal'] = subtotal
            valor_total += subtotal

        dados['valorTotal'] = valor_total

        # Salvar no banco de dados
        numero_pedido = salvar_pedido(dados)
        if not numero_pedido:
            return jsonify({'success': False, 'error': 'Erro ao salvar pedido no banco de dados'}), 500

        print(f"✅ Pedido {numero_pedido} salvo no banco")

        # Gerar PDF
        pdf_buffer = gerar_pdf_pedido(dados, numero_pedido)
        if not pdf_buffer:
            print("⚠️ Erro ao gerar PDF, mas pedido foi salvo")

        # Enviar email
        email_enviado = False
        if pdf_buffer:
            email_enviado = enviar_email_pedido_completo(
                dados, numero_pedido, pdf_buffer)

        return jsonify({
            'success': True,
            'numeroPedido': numero_pedido,
            'emailEnviado': email_enviado,
            'valorTotal': valor_total
        })

    except Exception as e:
        print(f"❌ Erro ao processar pedido: {e}")
        import traceback
        print(f"🔍 Detalhes: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500


@app.route('/download_pdf/<numero_pedido>')
def download_pdf(numero_pedido):
    """Download do PDF do pedido"""
    try:
        # Buscar dados do pedido no banco
        conn = conectar_postgresql()
        if not conn:
            return "Erro de conexão com banco", 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, c.razao_social, c.telefone 
            FROM pedidos p 
            LEFT JOIN clientes c ON p.cnpj_cliente = c.cnpj 
            WHERE p.numero_pedido = %s
        """, (numero_pedido,))

        pedido = cursor.fetchone()
        if not pedido:
            return "Pedido não encontrado", 404

        # Buscar itens do pedido
        cursor.execute("""
            SELECT artigo, codigo, desenho_cor, metragem, preco, subtotal
            FROM itens_pedido ip
            JOIN pedidos p ON ip.pedido_id = p.id
            WHERE p.numero_pedido = %s
            ORDER BY ip.id
        """, (numero_pedido,))

        itens = cursor.fetchall()
        cursor.close()
        conn.close()

        # Montar dados para PDF
        dados_pedido = {
            'nomeRepresentante': pedido[2],
            'razaoSocial': pedido[16] if len(pedido) > 16 else 'Cliente',
            'cnpj': pedido[1],
            'telefone': pedido[17] if len(pedido) > 17 else '',
            'observacoes': pedido[3] or '',
            'valorTotal': float(pedido[4]) if pedido[4] else 0,
            'tipoPedido': pedido[5] or '',
            'numeroOP': pedido[6] or '',
            'tabelaPrecos': pedido[7] or '',
            'tipoProduto': pedido[8] or '',
            'tipoFrete': pedido[9] or '',
            'vendaTriangular': pedido[10] or '',
            'regimeRET': pedido[11] or '',
            'produtos': []
        }

        for item in itens:
            dados_pedido['produtos'].append({
                'artigo': item[0],
                'codigo': item[1],
                'desenho_cor': item[2],
                'metragem': float(item[3]),
                'preco': float(item[4]),
                'subtotal': float(item[5])
            })

        # Gerar PDF
        pdf_buffer = gerar_pdf_pedido(dados_pedido, numero_pedido)
        if not pdf_buffer:
            return "Erro ao gerar PDF", 500

        # Retornar PDF para download
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"Pedido_DTX_{numero_pedido}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"❌ Erro ao gerar PDF para download: {e}")
        return f"Erro ao gerar PDF: {str(e)}", 500


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


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - PostgreSQL Web")
        print("📡 Servidor rodando em: http://127.0.0.1:5001")
        print("🔗 Health check: http://127.0.0.1:5001/health")
        print("👥 Clientes: http://127.0.0.1:5001/clientes")
        print("💰 Preços: http://127.0.0.1:5001/precos")
        print("📋 Criar Pedido: http://127.0.0.1:5001/criar-pedido")
        print("-" * 50)

        app.run(host='0.0.0.0', port=5001, debug=True)
    else:
        print("❌ Falha na inicialização do banco de dados")
        print("🔧 Verifique as configurações do PostgreSQL")
