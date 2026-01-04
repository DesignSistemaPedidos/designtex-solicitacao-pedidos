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


def enviar_email_pedido_completo(dados_pedido, numero_pedido, pdf_buffer):
    """Enviar email com PDF do pedido para os destinatários corretos"""

    # CONFIGURAÇÕES DE EMAIL - CORRIGIDAS
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
        print("=" * 60)
        print(f"📧 INICIANDO ENVIO DE EMAIL")
        print(f"📤 De: {EMAIL_USER}")
        print(f"📥 Para: {', '.join(EMAIL_DESTINOS)}")
        print(f"📋 Pedido: #{numero_pedido}")
        print(f"👥 Cliente: {dados_pedido.get('razaoSocial', '')}")
        print("=" * 60)

        # Criar mensagem
        msg = MIMEMultipart('alternative')
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
                    {dados_pedido.get('observacoes', '').replace(chr(10), '<br>')}
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
                    <p style="margin: 5px 0; font-size: 14px;">Email gerado automaticamente</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Anexar HTML ao email
        part_html = MIMEText(corpo_html, 'html', 'utf-8')
        msg.attach(part_html)

        # Anexar PDF
        if pdf_buffer and len(pdf_buffer.getvalue()) > 0:
            pdf_buffer.seek(0)
            pdf_data = pdf_buffer.read()

            print(f"📎 Anexando PDF (tamanho: {len(pdf_data)} bytes)")

            part = MIMEBase('application', 'pdf')
            part.set_payload(pdf_data)
            encoders.encode_base64(part)

            # Nome do arquivo PDF
            nome_cliente = dados_pedido.get('razaoSocial', '').replace(
                ' ', '_').replace('/', '_')[:20]
            nome_arquivo = f"Pedido_DTX_{numero_pedido}_{nome_cliente}.pdf"

            part.add_header('Content-Disposition',
                            f'attachment; filename="{nome_arquivo}"')
            msg.attach(part)

            print("✅ PDF anexado com sucesso")
        else:
            print("⚠️ PDF vazio ou inválido")

        # ENVIAR EMAIL
        print("🔗 Conectando ao servidor SMTP...")

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            print("🔐 Iniciando TLS...")
            server.starttls()

            print("🔑 Fazendo login...")
            server.login(EMAIL_USER, EMAIL_PASS)

            print("📤 Enviando mensagem...")
            text = msg.as_string()
            server.sendmail(EMAIL_USER, EMAIL_DESTINOS, text)

            print("✅ EMAIL ENVIADO COM SUCESSO!")

        print("=" * 60)
        print("🎉 PROCESSO DE EMAIL FINALIZADO")
        print("=" * 60)
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ ERRO DE AUTENTICAÇÃO SMTP: {e}")
        print("🔧 Verifique se a senha de app do Gmail está correta")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ ERRO SMTP: {e}")
        return False
    except Exception as e:
        print(f"❌ ERRO GERAL ao enviar email: {str(e)}")
        import traceback
        print(f"🔍 Detalhes completos: {traceback.format_exc()}")
        return False


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

        cliente_table = Table(cliente_data, colWidths=[4*mm, 12*mm])
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

        condicoes_table = Table(condicoes_data, colWidths=[4*mm, 12*mm])
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
                               3*mm, 2*mm, 4*mm, 2*mm, 2.5*mm, 2.5*mm])
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
        import traceback
        print(f"Detalhes do erro PDF: {traceback.format_exc()}")
        return None


# FLASK APP
app = Flask(__name__)

# Armazenar dados temporários do pedido
pedidos_temp = {}


@app.route('/')
def home():
    """Página inicial"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DESIGNTEX TECIDOS - Railway PostgreSQL</title>
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
        <p class="subtitle">Sistema de Pedidos - Railway PostgreSQL</p>
        
        <div class="status">
            ✅ Sistema Funcionando - Railway PostgreSQL Conectado
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
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Novo Pedido - DESIGNTEX TECIDOS</title>
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
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1a5490 0%, #2d72b8 100%);
            color: white;
            padding: 25px;
            text-align: center;
        }
        .form-container {
            padding: 30px;
        }
        .section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 25px;
            border-left: 4px solid #1a5490;
        }
        .section h3 {
            color: #1a5490;
            margin-bottom: 20px;
            font-size: 1.3em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .form-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        .form-group {
            display: flex;
            flex-direction: column;
        }
        label {
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        input, select, textarea {
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #1a5490;
            box-shadow: 0 0 0 3px rgba(26,84,144,0.1);
        }
        .btn {
            background: #1a5490;
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            margin: 5px;
        }
        .btn:hover {
            background: #0f3a6b;
            transform: translateY(-2px);
        }
        .btn-success {
            background: #28a745;
        }
        .btn-success:hover {
            background: #218838;
        }
        .btn-danger {
            background: #dc3545;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .produtos-container {
            border: 2px dashed #ccc;
            border-radius: 10px;
            padding: 20px;
            margin-top: 15px;
        }
        .produto-item {
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .total-container {
            background: #e8f5e8;
            border: 2px solid #28a745;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            margin-top: 20px;
        }
        .total-value {
            font-size: 24px;
            font-weight: bold;
            color: #28a745;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1a5490;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .autocomplete-container {
            position: relative;
        }
        .autocomplete-list {
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
            border-radius: 0 0 8px 8px;
        }
        .autocomplete-item {
            padding: 10px;
            cursor: pointer;
            border-bottom: 1px solid #eee;
        }
        .autocomplete-item:hover {
            background: #f0f0f0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏭 DESIGNTEX TECIDOS</h1>
            <h2>📋 Novo Pedido de Vendas</h2>
        </div>

        <div class="form-container">
            <form id="pedidoForm">
                <!-- SEÇÃO: REPRESENTANTE -->
                <div class="section">
                    <h3>👤 Dados do Representante</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="nomeRepresentante">Nome do Representante *</label>
                            <input type="text" id="nomeRepresentante" name="nomeRepresentante" required>
                        </div>
                        <div class="form-group">
                            <label for="prazoPagamento">Prazo de Pagamento *</label>
                            <select id="prazoPagamento" name="prazoPagamento" required>
                                <option value="">Selecione...</option>
                                <option value="À Vista">À Vista</option>
                                <option value="28 DDL">28 DDL</option>
                                <option value="35 DDL">35 DDL</option>
                                <option value="45 DDL">45 DDL</option>
                                <option value="60 DDL">60 DDL</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- SEÇÃO: CLIENTE -->
                <div class="section">
                    <h3>🏢 Dados do Cliente</h3>
                    <div class="form-row">
                        <div class="form-group autocomplete-container">
                            <label for="buscarCliente">Buscar Cliente *</label>
                            <input type="text" id="buscarCliente" placeholder="Digite razão social, CNPJ ou nome fantasia...">
                            <div id="listaClientes" class="autocomplete-list" style="display: none;"></div>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="cnpj">CNPJ *</label>
                            <input type="text" id="cnpj" name="cnpj" readonly>
                        </div>
                        <div class="form-group">
                            <label for="razaoSocial">Razão Social *</label>
                            <input type="text" id="razaoSocial" name="razaoSocial" readonly>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="nomeFantasia">Nome Fantasia</label>
                            <input type="text" id="nomeFantasia" name="nomeFantasia" readonly>
                        </div>
                        <div class="form-group">
                            <label for="telefone">Telefone</label>
                            <input type="text" id="telefone" name="telefone">
                        </div>
                    </div>
                </div>

                <!-- SEÇÃO: CONDIÇÕES -->
                <div class="section">
                    <h3>⚙️ Condições do Pedido</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="tipoPedido">Tipo de Pedido *</label>
                            <select id="tipoPedido" name="tipoPedido" required>
                                <option value="">Selecione...</option>
                                <option value="Normal">Normal</option>
                                <option value="Especial">Especial</option>
                                <option value="Amostra">Amostra</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="numeroOP">Número da OP</label>
                            <input type="text" id="numeroOP" name="numeroOP" placeholder="Opcional">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="tabelaPrecos">Tabela de Preços *</label>
                            <select id="tabelaPrecos" name="tabelaPrecos" required>
                                <option value="">Selecione...</option>
                                <option value="Normal">Normal</option>
                                <option value="LD">LD (Lista Descontada)</option>
                                <option value="Promocional">Promocional</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="tipoProduto">Tipo de Produto *</label>
                            <select id="tipoProduto" name="tipoProduto" required>
                                <option value="">Selecione...</option>
                                <option value="Tecido Plano">Tecido Plano</option>
                                <option value="Malha">Malha</option>
                                <option value="Acabamento">Acabamento</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="tipoFrete">Tipo de Frete *</label>
                            <select id="tipoFrete" name="tipoFrete" required>
                                <option value="">Selecione...</option>
                                <option value="CIF">CIF (Por conta do remetente)</option>
                                <option value="FOB">FOB (Por conta do destinatário)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="vendaTriangular">Venda Triangular?</label>
                            <select id="vendaTriangular" name="vendaTriangular">
                                <option value="Não">Não</option>
                                <option value="Sim">Sim</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="regimeRET">Regime RET?</label>
                            <select id="regimeRET" name="regimeRET">
                                <option value="Não">Não</option>
                                <option value="Sim">Sim</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- SEÇÃO: PRODUTOS -->
                <div class="section">
                    <h3>📦 Produtos</h3>
                    <button type="button" id="adicionarProduto" class="btn btn-success">➕ Adicionar Produto</button>
                    
                    <div id="produtosContainer" class="produtos-container">
                        <p style="text-align: center; color: #666; margin: 20px 0;">
                            Clique em "Adicionar Produto" para inserir itens no pedido
                        </p>
                    </div>

                    <div id="totalContainer" class="total-container" style="display: none;">
                        <h3>💰 Total do Pedido</h3>
                        <div class="total-value" id="valorTotal">R$ 0,00</div>
                    </div>
                </div>

                <!-- SEÇÃO: OBSERVAÇÕES -->
                <div class="section">
                    <h3>📝 Observações</h3>
                    <div class="form-group">
                        <label for="observacoes">Observações Adicionais</label>
                        <textarea id="observacoes" name="observacoes" rows="4" placeholder="Digite observações adicionais sobre o pedido..."></textarea>
                    </div>
                </div>

                <!-- BOTÕES -->
                <div style="text-align: center; padding: 20px;">
                    <button type="submit" id="enviarPedido" class="btn btn-success" style="font-size: 16px; padding: 15px 30px;">
                        📤 ENVIAR PEDIDO
                    </button>
                    <button type="button" onclick="window.location.href='/'" class="btn" style="background: #6c757d;">
                        ↩️ Voltar ao Início
                    </button>
                </div>

                <!-- LOADING -->
                <div id="loading" class="loading">
                    <div class="spinner"></div>
                    <p>Processando pedido...</p>
                </div>
            </form>
        </div>
    </div>

    <script>
        let produtos = [];
        let contadorProdutos = 0;

        // AUTOCOMPLETE CLIENTES
        document.getElementById('buscarCliente').addEventListener('input', function() {
            const query = this.value.trim();
            const lista = document.getElementById('listaClientes');

            if (query.length < 1) {
                lista.style.display = 'none';
                return;
            }

            fetch(`/api/buscar_clientes?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(clientes => {
                    lista.innerHTML = '';
                    
                    if (clientes.length === 0) {
                        lista.innerHTML = '<div class="autocomplete-item">Nenhum cliente encontrado</div>';
                        lista.style.display = 'block';
                        return;
                    }

                    clientes.forEach(cliente => {
                        const item = document.createElement('div');
                        item.className = 'autocomplete-item';
                        item.innerHTML = `
                            <strong>${cliente.razao_social}</strong><br>
                            <small>${cliente.cnpj} - ${cliente.nome_fantasia}</small>
                        `;
                        item.addEventListener('click', () => {
                            document.getElementById('cnpj').value = cliente.cnpj;
                            document.getElementById('razaoSocial').value = cliente.razao_social;
                            document.getElementById('nomeFantasia').value = cliente.nome_fantasia;
                            document.getElementById('telefone').value = cliente.telefone || '';
                            document.getElementById('buscarCliente').value = cliente.razao_social;
                            lista.style.display = 'none';
                        });
                        lista.appendChild(item);
                    });

                    lista.style.display = 'block';
                })
                .catch(error => {
                    console.error('Erro ao buscar clientes:', error);
                });
        });

        // Esconder lista quando clicar fora
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.autocomplete-container')) {
                document.getElementById('listaClientes').style.display = 'none';
            }
        });

        // ADICIONAR PRODUTO
        document.getElementById('adicionarProduto').addEventListener('click', function() {
            contadorProdutos++;
            
            const produtoHtml = `
                <div class="produto-item" data-produto-id="${contadorProdutos}">
                    <h4>🧵 Produto ${contadorProdutos}</h4>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Artigo *</label>
                            <input type="text" class="produto-artigo" required placeholder="Ex: ALGODÃO 30/1">
                        </div>
                        <div class="form-group">
                            <label>Código *</label>
                            <input type="text" class="produto-codigo" required placeholder="Ex: ALG301">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Desenho/Cor *</label>
                            <input type="text" class="produto-desenho" required placeholder="Ex: LISO AZUL MARINHO">
                        </div>
                        <div class="form-group">
                            <label>Metragem *</label>
                            <input type="number" class="produto-metragem" step="0.01" min="0" required placeholder="0.00">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Preço Unitário (R$) *</label>
                            <input type="number" class="produto-preco" step="0.01" min="0" required placeholder="0.00">
                        </div>
                        <div class="form-group">
                            <label>Subtotal (R$)</label>
                            <input type="text" class="produto-subtotal" readonly style="background: #f0f0f0;">
                        </div>
                    </div>
                    <button type="button" class="btn btn-danger" onclick="removerProduto(${contadorProdutos})">
                        🗑️ Remover Produto
                    </button>
                </div>
            `;

            document.getElementById('produtosContainer').innerHTML = 
                document.getElementById('produtosContainer').innerHTML.replace(
                    '<p style="text-align: center; color: #666; margin: 20px 0;">Clique em "Adicionar Produto" para inserir itens no pedido</p>',
                    ''
                ) + produtoHtml;

            // Adicionar eventos de cálculo
            const produtoItem = document.querySelector(`[data-produto-id="${contadorProdutos}"]`);
            const metragemInput = produtoItem.querySelector('.produto-metragem');
            const precoInput = produtoItem.querySelector('.produto-preco');
            
            [metragemInput, precoInput].forEach(input => {
                input.addEventListener('input', () => calcularSubtotalProduto(contadorProdutos));
            });

            document.getElementById('totalContainer').style.display = 'block';
        });

        // REMOVER PRODUTO
        function removerProduto(id) {
            const produtoItem = document.querySelector(`[data-produto-id="${id}"]`);
            if (produtoItem) {
                produtoItem.remove();
                calcularTotal();
                
                // Se não há mais produtos, esconder total
                if (document.querySelectorAll('.produto-item').length === 0) {
                    document.getElementById('produtosContainer').innerHTML = 
                        '<p style="text-align: center; color: #666; margin: 20px 0;">Clique em "Adicionar Produto" para inserir itens no pedido</p>';
                    document.getElementById('totalContainer').style.display = 'none';
                }
            }
        }

        // CALCULAR SUBTOTAL DO PRODUTO
        function calcularSubtotalProduto(id) {
            const produtoItem = document.querySelector(`[data-produto-id="${id}"]`);
            const metragem = parseFloat(produtoItem.querySelector('.produto-metragem').value) || 0;
            const preco = parseFloat(produtoItem.querySelector('.produto-preco').value) || 0;
            const subtotal = metragem * preco;
            
            produtoItem.querySelector('.produto-subtotal').value = `R$ ${subtotal.toFixed(2)}`;
            calcularTotal();
        }

        // CALCULAR TOTAL GERAL
        function calcularTotal() {
            let total = 0;
            document.querySelectorAll('.produto-item').forEach(item => {
                const metragem = parseFloat(item.querySelector('.produto-metragem').value) || 0;
                const preco = parseFloat(item.querySelector('.produto-preco').value) || 0;
                total += metragem * preco;
            });
            
            document.getElementById('valorTotal').textContent = `R$ ${total.toFixed(2)}`;
        }

        // ENVIAR PEDIDO
        document.getElementById('pedidoForm').addEventListener('submit', function(e) {
            e.preventDefault();

            // Validar se há produtos
            if (document.querySelectorAll('.produto-item').length === 0) {
                alert('Adicione pelo menos um produto ao pedido!');
                return;
            }

            // Coletar dados do formulário
            const formData = new FormData(this);
            const dados = {};
            
            // Dados básicos
            for (let [key, value] of formData.entries()) {
                dados[key] = value;
            }

            // Coletar produtos
            dados.produtos = [];
            document.querySelectorAll('.produto-item').forEach(item => {
                const metragem = parseFloat(item.querySelector('.produto-metragem').value) || 0;
                const preco = parseFloat(item.querySelector('.produto-preco').value) || 0;
                
                dados.produtos.push({
                    artigo: item.querySelector('.produto-artigo').value,
                    codigo: item.querySelector('.produto-codigo').value,
                    desenho_cor: item.querySelector('.produto-desenho').value,
                    metragem: metragem,
                    preco: preco,
                    subtotal: metragem * preco
                });
            });

            // Calcular total
            dados.valorTotal = dados.produtos.reduce((total, produto) => total + produto.subtotal, 0);

            // Mostrar loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('enviarPedido').disabled = true;

            // Enviar para servidor
            fetch('/submit_pedido', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(dados)
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                
                if (data.sucesso) {
                    alert(`Pedido ${data.numero_pedido} enviado com sucesso!`);
                    window.location.href = data.redirect_url;
                } else {
                    alert('Erro ao enviar pedido: ' + (data.erro || 'Erro desconhecido'));
                    document.getElementById('enviarPedido').disabled = false;
                }
            })
            .catch(error => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('enviarPedido').disabled = false;
                console.error('Erro:', error);
                alert('Erro ao enviar pedido. Tente novamente.');
            });
        });
    </script>
</body>
</html>
    ''')


@app.route('/pedido-sucesso/<numero_pedido>')
def pedido_sucesso(numero_pedido):
    """Tela de confirmação com opção de download"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pedido Enviado - DESIGNTEX</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
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
            color: #28a745;
            margin-bottom: 20px;
            font-size: 2.5em;
        }
        .sucesso-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        .info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: left;
        }
        .btn {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 25px;
            margin: 10px;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        .btn.secondary {
            background: #6c757d;
        }
        .btn.secondary:hover {
            background: #545b62;
        }
        .email-status {
            background: #d1ecf1;
            color: #0c5460;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            border: 1px solid #bee5eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sucesso-icon">✅</div>
        <h1>Pedido Enviado!</h1>
        
        <div class="info">
            <h3>📋 Detalhes do Pedido:</h3>
            <p><strong>Número:</strong> #{{ numero_pedido }}</p>
            <p><strong>Data/Hora:</strong> {{ datetime.now().strftime('%d/%m/%Y às %H:%M:%S') }}</p>
        </div>
        
        <div class="email-status">
            <h4>📧 Status do Email:</h4>
            <p>✅ Pedido enviado automaticamente para:</p>
            <ul style="text-align: left; margin-top: 10px;">
                <li>pedido@designtextecidos.com.br</li>
                <li>design2@designtextecidos.com.br</li>
            </ul>
        </div>
        
        <div style="margin: 30px 0;">
            <a href="/download-pdf/{{ numero_pedido }}" class="btn">📄 BAIXAR PDF</a>
            <a href="/criar-pedido" class="btn secondary">📋 NOVO PEDIDO</a>
            <a href="/" class="btn secondary">🏠 VOLTAR AO INÍCIO</a>
        </div>
        
        <div class="info">
            <h4>🔔 Próximos Passos:</h4>
            <ol style="text-align: left; margin-top: 10px;">
                <li>Baixe o PDF para seus registros</li>
                <li>Aguarde confirmação por email da DESIGNTEX</li>
                <li>Acompanhe o processamento do pedido</li>
            </ol>
        </div>
    </div>
</body>
</html>
    ''', numero_pedido=numero_pedido, datetime=datetime)


@app.route('/download-pdf/<numero_pedido>')
def download_pdf(numero_pedido):
    """Download do PDF do pedido"""
    try:
        # Buscar dados do pedido no storage temporário
        if numero_pedido not in pedidos_temp:
            return jsonify({'erro': 'Pedido não encontrado'}), 404

        dados_pedido = pedidos_temp[numero_pedido]

        # Gerar PDF
        pdf_buffer = gerar_pdf_pedido(dados_pedido, numero_pedido)

        if not pdf_buffer:
            return jsonify({'erro': 'Erro ao gerar PDF'}), 500

        # Nome do arquivo
        nome_cliente = dados_pedido.get('razaoSocial', '').replace(
            ' ', '_').replace('/', '_')[:20]
        nome_arquivo = f"Pedido_DTX_{numero_pedido}_{nome_cliente}.pdf"

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=nome_arquivo,
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"Erro no download do PDF: {e}")
        return jsonify({'erro': 'Erro interno do servidor'}), 500


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Processar envio do pedido"""
    try:
        print("🔄 Iniciando processamento do pedido...")

        dados = request.get_json()

        # Validações básicas
        if not dados:
            return jsonify({'erro': 'Dados não recebidos'}), 400

        # Salvar no banco
        print("💾 Salvando pedido no banco...")
        numero_pedido = salvar_pedido(dados)

        if not numero_pedido:
            return jsonify({'erro': 'Erro ao salvar pedido no banco'}), 500

        # Gerar PDF
        print("📄 Gerando PDF...")
        pdf_buffer = gerar_pdf_pedido(dados, numero_pedido)

        if not pdf_buffer:
            return jsonify({'erro': 'Erro ao gerar PDF'}), 500

        # Salvar dados temporariamente para download posterior
        pedidos_temp[numero_pedido] = dados

        # Enviar email
        print("📧 Enviando email...")
        email_enviado = enviar_email_pedido_completo(
            dados, numero_pedido, pdf_buffer)

        if email_enviado:
            print("✅ Email enviado com sucesso!")
            email_status = "enviado"
        else:
            print("⚠️ Erro no envio do email")
            email_status = "erro"

        print(f"🎉 Pedido #{numero_pedido} processado com sucesso!")

        return jsonify({
            'sucesso': True,
            'numero_pedido': numero_pedido,
            'email_status': email_status,
            'redirect_url': f'/pedido-sucesso/{numero_pedido}'
        })

    except Exception as e:
        print(f"❌ Erro no submit_pedido: {e}")
        import traceback
        print(f"🔍 Trace completo: {traceback.format_exc()}")

        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500


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
                'database': 'Railway PostgreSQL - Conectado',
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
            'database': 'Railway PostgreSQL - Desconectado',
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
            'telefone': cliente[3]
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
    """API para buscar clientes (autocomplete)"""
    query = request.args.get('q', '').strip()

    if len(query) < 1:
        return jsonify([])

    clientes = buscar_clientes()
    clientes_filtrados = []

    for cliente in clientes:
        cnpj, razao, fantasia, telefone = cliente

        # Buscar em razão social e nome fantasia
        if (query.lower() in razao.lower() or
            query.lower() in fantasia.lower() or
                query in cnpj):

            clientes_filtrados.append({
                'cnpj': cnpj,
                'razao_social': razao,
                'nome_fantasia': fantasia,
                'telefone': telefone
            })

    return jsonify(clientes_filtrados[:10])  # Limitar a 10 resultados


if __name__ == '__main__':
    # Inicializar banco de dados
    if init_database():
        print("🚀 Iniciando DESIGNTEX TECIDOS - Railway PostgreSQL")
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
