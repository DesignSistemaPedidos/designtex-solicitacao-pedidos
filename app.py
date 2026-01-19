import click
from threading import Lock
import os
import sys
import locale
import json
import io
import psycopg2
from urllib.parse import urlparse
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file, current_app
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging
logging.basicConfig(level=logging.DEBUG)

# -----------------------------------------------------------------------------
# Config util
# -----------------------------------------------------------------------------


def get_port_and_host():
    host = '0.0.0.0'
    port = int(os.getenv('PORT', 8080))  # Railway define PORT
    env = os.getenv('ENVIRONMENT', 'development').lower()
    debug = env != 'production'
    print(f"🌐 Ambiente: {env} | Porta: {port} | Debug: {debug}")
    return host, port, debug


def configurar_encoding():
    try:
        if sys.platform.startswith('win'):
            os.system('chcp 65001 > nul')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        # Remover forçação de client encoding via env:
        os.environ.pop('PGCLIENTENCODING', None)
        try:
            locale.setlocale(locale.LC_ALL, 'C')
        except:
            pass
        print("✅ Encoding configurado com sucesso")
    except Exception as e:
        print(f"⚠️  Aviso na configuração de encoding: {e}")


configurar_encoding()

# -----------------------------------------------------------------------------
# Email (use variáveis de ambiente em produção)
# -----------------------------------------------------------------------------
EMAIL_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASS = os.getenv('EMAIL_PASSWORD', '')
EMAIL_DESTINOS = os.getenv(
    'EMAIL_TO', 'pedido@designtextecidos.com.br,design2@designtextecidos.com.br').split(',')


def enviar_email_pedido_completo(dados_pedido, numero_pedido, pdf_buffer):
    try:
        if not EMAIL_USER or not EMAIL_PASS:
            print("⚠️ EMAIL_USER/EMAIL_PASSWORD não configurados. Pulando envio.")
            return False

        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ', '.join(EMAIL_DESTINOS)
        msg['Subject'] = f"🏭 NOVO PEDIDO DTX #{numero_pedido} - {dados_pedido.get('razaoSocial', '')[:30]}"

        corpo_html = f"""
        <html><body style="font-family: Arial, sans-serif; line-height:1.6; color:#333;">
            <div style="background:#1a5490;color:white;padding:10px;text-align:center;">
                <h1>🏭 DESIGNTEX TECIDOS</h1>
                <h2>NOVA SOLICITAÇÃO DE PEDIDO DE VENDAS</h2>
            </div>
            <div style="padding:10px;">
                <h3 style="color:#1a5490;">📋 DADOS DO PEDIDO</h3>
                <table style="width:100%;border-collapse:collapse;margin-bottom:10px;">
                    <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Número:</td>
                        <td style="padding:8px;border:1px solid #ddd;">#{numero_pedido}</td></tr>
                    <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Representante:</td>
                        <td style="padding:8px;border:1px solid #ddd;">{dados_pedido.get('nomeRepresentante', '')}</td></tr>
                    <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Cliente:</td>
                        <td style="padding:8px;border:1px solid #ddd;">{dados_pedido.get('razaoSocial', '')}</td></tr>
                    <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">CNPJ:</td>
                        <td style="padding:8px;border:1px solid #ddd;">{dados_pedido.get('cnpj', '')}</td></tr>
                    <tr><td style="padding:8px;border:1px solid #ddd;background:#f9f9f9;font-weight:bold;">Valor Total:</td>
                        <td style="padding:8px;border:1px solid #ddd;"><strong>R$ {dados_pedido.get('valorTotal', 0):.2f}</strong></td></tr>
                </table>
                <div style="text-align:center;margin-top:15px;padding:10px;background:#1a5490;color:white;">
                    <p style="margin:0;"><strong>Sistema de Pedidos DESIGNTEX TECIDOS</strong></p>
                    <p style="margin:5px 0;font-size:12px;">Recebido em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
                </div>
            </div>
        </body></html>
        """
        msg.attach(MIMEText(corpo_html, 'html'))

        if pdf_buffer and pdf_buffer.getvalue():
            pdf_buffer.seek(0)
            part = MIMEBase('application', 'pdf')
            part.set_payload(pdf_buffer.read())
            encoders.encode_base64(part)
            nome_arquivo = f"Pedido_DTX_{numero_pedido}_{dados_pedido.get('razaoSocial', '').replace(' ', '_').replace('/', '_')[:20]}.pdf"
            part.add_header('Content-Disposition',
                            f'attachment; filename="{nome_arquivo}"')
            msg.attach(part)

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_DESTINOS, msg.as_string())
        server.quit()
        print("✅ Email enviado")
        return True
    except Exception as e:
        print(f"❌ ERRO ao enviar email: {e}")
        return False

# -----------------------------------------------------------------------------
# DB
# -----------------------------------------------------------------------------


def get_database_config():
    """Obter configuração do banco baseada no ambiente (Local x Produção/Railway)."""
    environment = (os.getenv('ENVIRONMENT') or 'development').lower()

    # Aceita várias chaves comuns em plataformas
    db_url = (
        os.getenv('DATABASE_URL') or
        os.getenv('POSTGRES_URL') or
        os.getenv('PGURL')
    )

    def _sanitize_url(url: str) -> str:
        # psycopg2 aceita postgresql://; normaliza se vier postgres://
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        # Força SSL em produção (Railway normalmente requer)
        if 'sslmode=' not in url:
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}sslmode=require"
        return url

    if environment in ('prod', 'production') or db_url:
        print("🌐 Configuração PRODUÇÃO (Railway/Cloud)")

        if db_url:
            db_url = _sanitize_url(db_url)
            # Não expor credenciais no log
            print("→ Usando DATABASE_URL (sanitizado), sslmode=require habilitado")
            return {'database_url': db_url}

        # Sem DATABASE_URL: monta via variáveis padrão de Railway/PG
        host = os.getenv('RAILWAY_DB_HOST') or os.getenv('PGHOST')
        database = os.getenv('RAILWAY_DB_NAME') or os.getenv(
            'PGDATABASE') or 'railway'
        user = os.getenv('RAILWAY_DB_USER') or os.getenv(
            'PGUSER') or 'postgres'
        password = os.getenv('RAILWAY_DB_PASSWORD') or os.getenv('PGPASSWORD')
        port = int(os.getenv('RAILWAY_DB_PORT') or os.getenv('PGPORT') or 5432)

        print(
            f"→ Host: {host} | DB: {database} | User: {user} | Port: {port} | sslmode=require")
        return {
            'host': host,
            'database': database,
            'user': user,
            'password': password,
            'port': port,
            'sslmode': 'require',
            'client_encoding': 'UTF8',
            'connect_timeout': 30
        }

    # Desenvolvimento (Local)
    print("🏠 Configuração DESENVOLVIMENTO (Local)")
    host = os.getenv('LOCAL_DB_HOST', 'localhost')
    database = os.getenv('LOCAL_DB_NAME', 'designtex_db')
    user = os.getenv('LOCAL_DB_USER', 'postgres')
    password = os.getenv('LOCAL_DB_PASSWORD', 'postgres')
    port = int(os.getenv('LOCAL_DB_PORT', 5432))

    print(f"→ Host: {host} | DB: {database} | User: {user} | Port: {port}")
    return {
        'host': host,
        'database': database,
        'user': user,
        'password': password,
        'port': port,
        'client_encoding': 'UTF8',
        'connect_timeout': 30
    }


DATABASE_CONFIG = get_database_config()


def conectar_postgresql():
    encodings_para_testar = ['UTF8', 'LATIN1', 'WIN1252', 'SQL_ASCII']

    for encoding in encodings_para_testar:
        try:
            print(f"🔄 Tentando conectar com encoding: {encoding}")
            if 'database_url' in DATABASE_CONFIG:
                database_url = DATABASE_CONFIG['database_url']
                url_com_encoding = f"{database_url}{'&' if '?' in database_url else '?'}client_encoding={encoding}"
                conn = psycopg2.connect(url_com_encoding)
            else:
                config = DATABASE_CONFIG.copy()
                config['client_encoding'] = encoding
                conn = psycopg2.connect(**config)

            conn.set_client_encoding(encoding)
            cur = conn.cursor()
            cur.execute('SELECT 1;')
            cur.fetchone()
            cur.close()
            print(f"✅ Conectado com sucesso usando encoding: {encoding}")
            return conn

        except UnicodeDecodeError as e:
            print(
                "❌ Falha de decode de mensagem (provável erro de conexão local com mensagem em pt-BR/cp1252).")
            print(
                "   Dica: verifique serviço do PostgreSQL, senha/porta e evite PGCLIENTENCODING=SQL_ASCII.")
            continue
        except Exception as e:
            print(f"❌ Erro com encoding {encoding}: {repr(e)[:200]}...")
            continue

    print("❌ Não foi possível conectar com nenhum encoding")
    return None


def init_database():
    print("🔄 Inicializando PostgreSQL...")
    conn = conectar_postgresql()
    if not conn:
        print("❌ Falha na conexão inicial")
        return False
    try:
        cur = conn.cursor()
        try:
            cur.execute("SET client_encoding TO 'SQL_ASCII';")
            cur.execute("SET standard_conforming_strings TO on;")
        except:
            pass

        # Criação de tabelas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                cnpj VARCHAR(18) UNIQUE NOT NULL,
                razao_social VARCHAR(200) NOT NULL,
                nome_fantasia VARCHAR(150),
                telefone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
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
        cur.execute("""
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sequencia_pedidos (
                id INTEGER PRIMARY KEY DEFAULT 1,
                ultimo_numero INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            INSERT INTO sequencia_pedidos (id, ultimo_numero)
            VALUES (1, 0)
            ON CONFLICT (id) DO NOTHING
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS precos_normal (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                icms_18 DECIMAL(10,2),
                icms_12 DECIMAL(10,2),
                icms_7 DECIMAL(10,2),
                ret_mg DECIMAL(10,2),
                observacao VARCHAR(30)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS precos_ld (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(200),
                codigo VARCHAR(50) UNIQUE,
                preco DECIMAL(10,2),
                observacao VARCHAR(30)
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Tabelas OK")
        return True
    except Exception as e:
        print(f"❌ Erro ao inicializar database: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False


def obter_proximo_numero_pedido():
    conn = conectar_postgresql()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE sequencia_pedidos SET ultimo_numero = ultimo_numero + 1 WHERE id = 1 RETURNING ultimo_numero")
        numero = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return str(numero).zfill(4)
    except Exception as e:
        print(f"Erro ao obter número do pedido: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return None


def salvar_pedido(dados_pedido):
    conn = conectar_postgresql()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        numero_pedido = obter_proximo_numero_pedido()
        if not numero_pedido:
            return None

        cur.execute("""
            INSERT INTO pedidos (
                numero_pedido, cnpj_cliente, representante, observacoes,
                valor_total, tipo_pedido, numero_op, tabela_precos,
                tipo_produto, tipo_frete, venda_triangular, regime_ret, dados_json
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            json.dumps(dados_pedido, ensure_ascii=False)
        ))
        pedido_id = cur.fetchone()[0]

        for produto in dados_pedido.get('produtos', []):
            cur.execute("""
                INSERT INTO itens_pedido (pedido_id, artigo, codigo, desenho_cor, metragem, preco, subtotal)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
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
        cur.close()
        conn.close()
        return numero_pedido
    except Exception as e:
        print(f"Erro ao salvar pedido: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return None


def gerar_pdf_pedido(dados_pedido, numero_pedido):
    """Gerar PDF do pedido com logo e condições do pedido"""
    import io
    from datetime import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm, cm

    # Caminho absoluto do logo (dentro de /static)
    logo_abspath = os.path.join(
        current_app.root_path, 'static', 'logo-dtx.png')
    EMPRESA_INFOS = [
        "Telefone: (31) 3286-2853",
        "Endereço: Av. Barão Homem de Melo, 1275 - Nova Granada - Belo Horizonte/MG - 30431-285",
        "CNPJ: 13.016.585/0001-80"
    ]

    buffer = io.BytesIO()
    try:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=10*mm, leftMargin=10*mm,
            topMargin=10*mm, bottomMargin=10*mm
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Centralizado',
                   parent=styles['Normal'], alignment=1))
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=10, alignment=1)
        info_style = ParagraphStyle(
            'EmpresaInfo', parent=styles['Normal'], fontSize=9, alignment=1, spaceAfter=2)

        story = []

        # Logo + Infos
        try:
            if os.path.exists(logo_abspath):
                img = Image(logo_abspath, width=200, height=59)
                img.hAlign = 'CENTER'
                story.append(img)
            else:
                print(f"⚠️ Logo não encontrado em: {logo_abspath}")
                story.append(
                    Paragraph("<b>DESIGNTEX TECIDOS</b>", title_style))
        except Exception as img_e:
            print(f"⚠️ Erro ao carregar logo: {img_e}")
            story.append(Paragraph("<b>DESIGNTEX TECIDOS</b>", title_style))

        for info in EMPRESA_INFOS:
            story.append(Paragraph(info, info_style))
        story.append(Spacer(1, 8))

        story.append(
            Paragraph(f"SOLICITAÇÃO DE PEDIDO DE VENDAS Nº {numero_pedido}", title_style))
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
        story.append(Spacer(1, 16))

        # Condições do pedido (dinâmico: inclui só o que vier preenchido)
        campos_condicoes = [
            ('Prazo de Pagamento:', dados_pedido.get('prazoPagamento')),
            ('Tabela de Preços:', dados_pedido.get('tabelaPrecos')),
            ('Tipo Pedido:', dados_pedido.get('tipoPedido')),
            ('Número OP:', dados_pedido.get('numeroOP')),
            ('Tipo Produto:', dados_pedido.get('tipoProduto')),
            ('Tipo Frete:', dados_pedido.get('tipoFrete')),
            ('Venda Triangular:', dados_pedido.get('vendaTriangular')),
            ('Regime RET:', dados_pedido.get('regimeRET')),
            ('Transportadora FOB:', dados_pedido.get('transportadoraFOB')),
            ('Transportadora CIF:', dados_pedido.get('transportadoraCIF')),
            ('Dados Triangulação:', dados_pedido.get('dadosTriangulacao')),
        ]
        condicoes_data = [['CONDIÇÕES DO PEDIDO', '']]
        for rotulo, valor in campos_condicoes:
            if valor not in (None, '', []):
                condicoes_data.append([rotulo, str(valor)])

        if len(condicoes_data) > 1:
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
            story.append(Spacer(1, 16))

        # Produtos
        produtos_data = [['Artigo', 'Código',
                          'Desenho/Cor', 'Metragem', 'Preço', 'Subtotal']]
        for produto in dados_pedido.get('produtos', []):
            produtos_data.append([
                produto.get('artigo', ''),
                produto.get('codigo', ''),
                produto.get('desenho_cor', ''),
                f"{(produto.get('metragem') or 0):.2f}",
                f"R$ {(produto.get('preco') or 0):.2f}",
                f"R$ {(produto.get('subtotal') or 0):.2f}"
            ])
        produtos_data.append(
            ['', '', '', '', 'TOTAL:', f"R$ {(dados_pedido.get('valorTotal') or 0):.2f}"])

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
        story.append(Spacer(1, 16))

        # Observações
        obs = dados_pedido.get('observacoes')
        if obs:
            story.append(Paragraph("OBSERVAÇÕES:", styles['Heading2']))
            story.append(Paragraph(obs, styles['Normal']))
            story.append(Spacer(1, 12))

        # Rodapé
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            f"Pedido gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "<b>Pedido sujeito à confirmação da Empresa Fornecedora.</b>", styles['Centralizado']))

        doc.build(story)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return None


# -----------------------------------------------------------------------------
# Flask app
# -----------------------------------------------------------------------------
app = Flask(__name__)


# Inicializa DB ao importar o módulo (produção)
if os.getenv('INIT_DB_ON_START', 'true').lower() == 'true':
    try:
        init_database()
    except Exception as e:
        print(f"⚠️ Erro ao inicializar DB no import: {e}")


@app.cli.command('init-db')
def cli_init_db():
    """Inicializa o banco (cria tabelas e dados iniciais)."""
    ok = init_database()
    if ok:
        click.echo('✅ Banco inicializado com sucesso')
    else:
        click.echo('❌ Falha na inicialização do banco', err=True)
        raise SystemExit(1)


_db_init_lock = Lock()
_db_initialized = False


def ensure_db_initialized():
    global _db_initialized
    if _db_initialized:
        return
    with _db_init_lock:
        if _db_initialized:
            return
        ok = init_database()
        if not ok:
            print("❌ Falha ao inicializar o banco")
        else:
            print("✅ Banco inicializado/validado")
        _db_initialized = True


# Preferível (Flask >= 2.2/2.3)
if hasattr(app, "before_serving"):
    @app.before_serving
    def _init_db_before_serving():
        ensure_db_initialized()
# Fallback para versões sem before_serving (ou se quiser garantir)
else:
    @app.before_request
    def _init_db_before_request():
        ensure_db_initialized()


@app.route('/health')
def health():
    """Health check - responde mesmo se DB estiver indisponível"""
    try:
        conn = conectar_postgresql()
        if conn:
            cur = conn.cursor()
            cur.execute('SELECT 1;')
            cur.fetchone()
            cur.close()
            conn.close()
            return jsonify({
                'status': 'OK',
                'database': 'connected',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'DEGRADED',
                'database': 'disconnected',
                'timestamp': datetime.now().isoformat()
            }), 200  # Retorna 200 mesmo sem DB para passar no healthcheck
    except Exception as e:
        return jsonify({
            'status': 'DEGRADED',
            'database': f'error: {str(e)[:50]}',
            'timestamp': datetime.now().isoformat()
        }), 200  # Retorna 200 para não falhar o healthcheck


@app.route('/')
def home():
    return render_template_string("""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Solicitação de Pedido de Vendas - Designtex Tecidos</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"/>
  <style>
    body { background-color:#80858b; font-family: Arial, sans-serif; }
    .container { background:#fff; border-radius:15px; padding:30px; margin:20px auto; box-shadow:0 4px 8px rgba(0,0,0,.2); max-width:1000px; }
    .header-title { color:#1a5490; text-align:center; font-weight:bold; margin-bottom:30px; font-size:28px; }
    .autocomplete-container { position:relative; }
    .autocomplete-dropdown { position:absolute; top:100%; left:0; right:0; background:#fff; border:1px solid #ddd; border-top:none; max-height:200px; overflow-y:auto; z-index:1000; display:none; }
    .autocomplete-item { padding:12px; border-bottom:1px solid #eee; cursor:pointer; font-size:14px; }
    .autocomplete-item:hover { background:#f5f5f5; }
    .btn-primary { background:#1a5490; border-color:#1a5490; }
    .btn-primary:hover { background:#134072; border-color:#134072; }
    .btn-voltar { background:#6c757d; color:#fff; text-decoration:none; padding:8px 16px; border-radius:5px; margin-bottom:20px; display:inline-block; }
    .btn-voltar:hover { background:#5a6268; color:#fff; text-decoration:none; }
    @media (max-width:768px) { .container { margin:10px; padding:20px; } .header-title { font-size:22px; } }
  </style>
</head>
<body>
  <div class="container">
    <a href="/" class="btn-voltar">⬅️ Voltar ao Início</a>
    <h1 class="header-title">SOLICITAÇÃO DE PEDIDO DE VENDAS<br/>DESIGNTEX TECIDOS</h1>

    <form id="pedidoForm">
      <!-- Cabeçalho -->
      <div class="card mb-4">
        <div class="card-header" style="background-color:#1a5490;color:#fff;"><h5 class="mb-0">📋 DADOS DO CABEÇALHO</h5></div>
        <div class="card-body">
          <div class="row g-3">
            <div class="col-md-6">
              <label for="nomeRepresentante" class="form-label">Nome do Representante *</label>
              <input type="text" class="form-control" id="nomeRepresentante" required/>
            </div>
            <div class="col-md-6">
              <label for="razaoSocial" class="form-label">Razão Social do Cliente *</label>
              <div class="autocomplete-container">
                <input type="text" class="form-control" id="razaoSocial" placeholder="Digite para buscar..." required/>
                <div id="autocomplete-dropdown" class="autocomplete-dropdown"></div>
              </div>
            </div>
            <div class="col-md-6">
              <label for="cnpj" class="form-label">CNPJ do Cliente *</label>
              <input type="text" class="form-control" id="cnpj" readonly style="background-color:#f8f9fa;"/>
            </div>
            <div class="col-md-6">
              <label for="telefone" class="form-label">Telefone de Contato *</label>
              <input type="text" class="form-control" id="telefone" required/>
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
                                <option>À vista</option>
                                <option>7 dias</option>
                                <option>14 dias</option>
                                <option>21 dias</option>
                                <option>28 dias</option>
                                <option>21/28/35 dias</option>
                                <option>35/42/49 dias</option>
                                <option>28/35/42/49/56 dias</option>
                                <option>49/56/63 dias</option>
                                <option>42/49/56/63/70 dias</option>
                                <option>56/63/70/77/84 dias</option>
                                <option>28/56/84/112/140 dias</option>
                                <option>56/70/84/98/112 dias</option>
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

      <!-- Tabela de preços -->
      <div class="card mb-4">
        <div class="card-header" style="background-color:#1a5490;color:#fff;"><h5 class="mb-0">💰 TABELA DE PREÇOS</h5></div>
        <div class="card-body">
          <div class="border p-3 rounded">
            <div class="form-check"><input class="form-check-input" type="radio" id="icms7"  name="tabelaPrecos" value="ICMS 7%" required><label for="icms7"  class="form-check-label me-3">ICMS 7%</label></div>
            <div class="form-check"><input class="form-check-input" type="radio" id="icms12" name="tabelaPrecos" value="ICMS 12%" required><label for="icms12" class="form-check-label me-3">ICMS 12%</label></div>
            <div class="form-check"><input class="form-check-input" type="radio" id="icms18" name="tabelaPrecos" value="ICMS 18%" required><label for="icms18" class="form-check-label me-3">ICMS 18%</label></div>
            <div class="form-check"><input class="form-check-input" type="radio" id="retmg"  name="tabelaPrecos" value="RET (SOMENTE MG)" required><label for="retmg"  class="form-check-label me-3">RET (SOMENTE MG)</label></div>
            <div class="form-check"><input class="form-check-input" type="radio" id="precosld" name="tabelaPrecos" value="PREÇOS LD (GERAL)" required><label for="precosld" class="form-check-label">PREÇOS LD (GERAL)</label></div>
            <small class="text-muted d-block mt-2">Selecione apenas uma opção.</small>
          </div>
        </div>
      </div>

      <!-- Produtos -->
      <div class="card mb-4">
        <div class="card-header" style="background-color:#1a5490;color:#fff;"><h5 class="mb-0">📦 PRODUTOS</h5></div>
        <div class="card-body">
          <div id="produtos-container"></div>
          <button type="button" class="btn btn-secondary mb-3" onclick="adicionarProduto()">➕ Adicionar Produto</button>
          <div class="text-end"><h4>Total: R$ <span id="valorTotal">0.00</span></h4></div>
        </div>
      </div>

      <!-- Observações -->
      <div class="card mb-4">
        <div class="card-header" style="background-color:#1a5490;color:#fff;"><h5 class="mb-0">📝 OBSERVAÇÕES</h5></div>
        <div class="card-body">
          <textarea class="form-control" id="observacoes" rows="4" maxlength="500" placeholder="Observações adicionais (máximo 500 caracteres)"></textarea>
          <div class="form-text"><span id="contadorCaracteres">0</span>/500 caracteres</div>
        </div>
      </div>

      <!-- Botões -->
      <div class="d-grid gap-2 d-md-flex justify-content-md-end">
        <button type="submit" class="btn btn-primary btn-lg me-md-2">📤 Enviar Pedido</button>
        <button type="button" class="btn btn-secondary btn-lg" onclick="limparFormulario()">🗑️ Cancelar</button>
      </div>
    </form>
  </div>

  <!-- Bootstrap JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
// ============================= VARIÁVEIS GLOBAIS =============================
let contadorProdutos = 0;
let listaArtigosComPrecos = [];
let tipoPrecoAtual = "";
let timeoutId;

// ============================= PRODUTOS DINÂMICOS ============================
function carregarArtigosDoBanco(callback) {
    fetch('/api/artigos_produto')
        .then(res => res.json())
        .then(dados => {
            listaArtigosComPrecos = dados;
            if (typeof callback === "function") callback();
        })
        .catch(err => console.error('Erro ao carregar artigos:', err));
}

function getTipoPrecoAtual() {
    const tabela = document.querySelector('input[name="tabelaPrecos"]:checked');
    if (!tabela) return "";
    const val = tabela.value;
    if (val.includes("7%")) return "icms_7";
    if (val.includes("12%")) return "icms_12";
    if (val.includes("18%")) return "icms_18";
    if (val.includes("RET")) return "ret_mg";
    if (val.includes("LD")) return "ld";
    return "";
}

function atualizarTodosPrecosProdutos() {
    document.querySelectorAll('[id^="produto-"]').forEach(prodDiv => {
        const pid = prodDiv.id.replace('produto-', '');
        const artigoSelect = prodDiv.querySelector(`select.artigo-select[data-produto="${pid}"]`);
        if (artigoSelect && artigoSelect.value) {
            preencherCodigoEPreco(pid, artigoSelect.value);
        }
    });
}

function atualizarTodasListasDeArtigos() {
    document.querySelectorAll('[id^="produto-"]').forEach(prodDiv => {
        const pid = prodDiv.id.replace('produto-', '');
        const artigoSelect = prodDiv.querySelector(`select.artigo-select[data-produto="${pid}"]`);
        if (artigoSelect) {
            let artigoAtual = artigoSelect.value;
            artigoSelect.innerHTML = `<option value="">Selecione...</option>`;
            gerarOpcoesArtigo().forEach(({ artigo }) => {
                const opt = document.createElement("option");
                opt.value = artigo;
                opt.textContent = artigo;
                artigoSelect.appendChild(opt);
            });
            if (artigoAtual) artigoSelect.value = artigoAtual;
        }
    });
}

function gerarOpcoesArtigo() {
    tipoPrecoAtual = getTipoPrecoAtual();
    return listaArtigosComPrecos.filter(a =>
        (tipoPrecoAtual === 'ld') ? a.tabela === 'ld' : a.tabela === 'normal'
    );
}

function adicionarProduto() {
    contadorProdutos++;
    const container = document.getElementById('produtos-container');
    const produtoDiv = document.createElement('div');
    produtoDiv.className = 'border rounded p-3 mb-3';
    produtoDiv.id = `produto-${contadorProdutos}`;

    produtoDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0">Produto ${contadorProdutos}</h6>
            <button type="button" class="btn btn-danger btn-sm" onclick="removerProduto(${contadorProdutos})">
                🗑️ Remover
            </button>
        </div>
        <div class="row">
            <div class="col-md-3 mb-2">
                <label class="form-label">Artigo *</label>
                <select class="form-select artigo-select" data-produto="${contadorProdutos}" required>
                    <option value="">Selecione...</option>
                </select>
            </div>
            <div class="col-md-2 mb-2">
                <label class="form-label">Código</label>
                <input type="text" class="form-control codigo-input" data-produto="${contadorProdutos}" readonly>
            </div>
            <div class="col-md-3 mb-2">
                <label class="form-label">Desenho/Cor *</label>
                <input type="text" class="form-control desenho-input" data-produto="${contadorProdutos}" required>
            </div>
            <div class="col-md-2 mb-2">
                <label class="form-label">Metragem *</label>
                <input type="number" class="form-control metragem-input" data-produto="${contadorProdutos}" min="0.01" step="0.01" required>
            </div>
            <div class="col-md-2 mb-2">
                <label class="form-label">Preço Unitário</label>
                <input type="number" class="form-control preco-input" data-produto="${contadorProdutos}" step="0.01" readonly>
            </div>
        </div>
        <div class="text-end">
            <strong>Subtotal: R$ <span class="subtotal" data-produto="${contadorProdutos}">0.00</span></strong>
        </div>
    `;
    container.appendChild(produtoDiv);

    const artigoSelect = produtoDiv.querySelector(`select.artigo-select[data-produto="${contadorProdutos}"]`);
    artigoSelect.innerHTML = `<option value="">Selecione...</option>`;
    gerarOpcoesArtigo().forEach(({ artigo }) => {
        const opt = document.createElement("option");
        opt.value = artigo;
        opt.textContent = artigo;
        artigoSelect.appendChild(opt);
    });

    adicionarEventListenersProduto(contadorProdutos);
}

function removerProduto(id) {
    const produto = document.getElementById(`produto-${id}`);
    if (produto) {
        produto.remove();
        calcularTotal();
    }
}

function adicionarEventListenersProduto(id) {
    const artigoSelect = document.querySelector(`select.artigo-select[data-produto="${id}"]`);
    artigoSelect.addEventListener('change', function() {
        preencherCodigoEPreco(id, this.value);
        calcularSubtotal(id);
    });
    const metragemInput = document.querySelector(`input.metragem-input[data-produto="${id}"]`);
    metragemInput.addEventListener('input', function() {
        calcularSubtotal(id);
    });
}

function preencherCodigoEPreco(id, artigoSelecionado) {
    tipoPrecoAtual = getTipoPrecoAtual();
    const artigoObj = listaArtigosComPrecos.find(a =>
        a.artigo === artigoSelecionado && (
           (tipoPrecoAtual === 'ld' && a.tabela === 'ld') ||
           (tipoPrecoAtual !== 'ld' && a.tabela === 'normal')
        )
    );
    const codigoInput = document.querySelector(`input.codigo-input[data-produto="${id}"]`);
    const precoInput = document.querySelector(`input.preco-input[data-produto="${id}"]`);
    if (artigoObj) {
        codigoInput.value = artigoObj.codigo || '';
        let preco = '';
        if (tipoPrecoAtual === 'ld') {
            preco = artigoObj.precos.ld ?? '';
        } else {
            preco = artigoObj.precos[tipoPrecoAtual] ?? '';
        }
        precoInput.value = preco !== null && preco !== '' ? parseFloat(preco).toFixed(2) : '';
    } else {
        codigoInput.value = '';
        precoInput.value = '';
    }
    calcularSubtotal(id);
}

function calcularSubtotal(produtoId) {
    const metragem = parseFloat(document.querySelector(`input.metragem-input[data-produto="${produtoId}"]`).value) || 0;
    const preco = parseFloat(document.querySelector(`input.preco-input[data-produto="${produtoId}"]`).value) || 0;
    const subtotal = metragem * preco;
    document.querySelector(`span.subtotal[data-produto="${produtoId}"]`).textContent = subtotal.toFixed(2);
    calcularTotal();
}

function calcularTotal() {
    let total = 0;
    document.querySelectorAll('.subtotal').forEach(span => {
        total += parseFloat(span.textContent) || 0;
    });
    document.getElementById('valorTotal').textContent = total.toFixed(2);
}

// ============================= AUTOCOMPLETE DE CLIENTES =======================
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
            console.error('❌ Erro na busca:', error);
        });
}

function mostrarResultados(clientes) {
    const dropdown = document.getElementById('autocomplete-dropdown');
    dropdown.innerHTML = '';

    if (!clientes || clientes.length === 0) {
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
        item.addEventListener('click', () => selecionarCliente(cliente));
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

function limparFormulario() {
    if (confirm('Deseja realmente cancelar e limpar todos os dados?')) {
        document.getElementById('pedidoForm').reset();
        document.getElementById('produtos-container').innerHTML = '';
        contadorProdutos = 0;
        calcularTotal();
        adicionarProduto();
    }
}

// ============================= EVENT LISTENERS =============================
document.addEventListener('click', function (e) {
    if (!e.target.closest('.autocomplete-container')) {
        document.getElementById('autocomplete-dropdown').style.display = 'none';
    }
});

document.querySelectorAll('input[name="tabelaPrecos"]').forEach(radio => {
    radio.addEventListener('change', function() {
        tipoPrecoAtual = getTipoPrecoAtual();
        atualizarTodosPrecosProdutos();
        atualizarTodasListasDeArtigos();
    });
});

const observacoesField = document.getElementById('observacoes');
if (observacoesField) {
    observacoesField.addEventListener('input', function() {
        const contador = document.getElementById('contadorCaracteres');
        if (contador) contador.textContent = this.value.length;
    });
}

document.getElementById('pedidoForm').addEventListener('submit', function(e) {
    e.preventDefault();

    if (contadorProdutos === 0) {
        alert('Adicione pelo menos um produto ao pedido!');
        return;
    }

    const dadosPedido = {
        nomeRepresentante: document.getElementById('nomeRepresentante').value,
        razaoSocial: document.getElementById('razaoSocial').value,
        cnpj: document.getElementById('cnpj').value,
        telefone: document.getElementById('telefone').value,
        prazoPagamento: document.getElementById('prazoPagamento').value,
        tabelaPrecos: document.querySelector('input[name="tabelaPrecos"]:checked')?.value,
        observacoes: document.getElementById('observacoes').value,
        produtos: [],
        valorTotal: parseFloat(document.getElementById('valorTotal').textContent)
    };

    document.querySelectorAll('[id^="produto-"]').forEach(produtoDiv => {
        const produtoId = produtoDiv.id.replace('produto-', '');
        const produto = {
            artigo: produtoDiv.querySelector(`select[data-produto="${produtoId}"]`).value,
            codigo: produtoDiv.querySelector(`input.codigo-input[data-produto="${produtoId}"]`).value,
            desenho_cor: produtoDiv.querySelector(`input.desenho-input[data-produto="${produtoId}"]`).value,
            metragem: parseFloat(produtoDiv.querySelector(`input.metragem-input[data-produto="${produtoId}"]`).value),
            preco: parseFloat(produtoDiv.querySelector(`input.preco-input[data-produto="${produtoId}"]`).value),
            subtotal: parseFloat(produtoDiv.querySelector(`span.subtotal[data-produto="${produtoId}"]`).textContent)
        };
        dadosPedido.produtos.push(produto);
    });

    fetch('/submit_pedido', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosPedido)
    })
    .then(r => r.json())
    .then(data => {
        if (data.sucesso) {
            alert(`Pedido enviado com sucesso! Número: ${data.numero_pedido}`);
            limparFormulario();
        } else {
            alert(`Erro ao enviar pedido: ${data.erro}`);
        }
    })
    .catch(err => {
        console.error('Erro:', err);
        alert('Erro ao enviar pedido. Tente novamente.');
    });
});

// ============================= INICIALIZAÇÃO =============================
window.addEventListener('load', function() {
    carregarArtigosDoBanco(() => {
        tipoPrecoAtual = getTipoPrecoAtual();
        adicionarProduto();
    });
});
</script>



</body>
</html>
    """)

# -----------------------------------------------------------------------------
# APIs
# -----------------------------------------------------------------------------


@app.route('/api/buscar_clientes')
def api_buscar_clientes():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    conn = conectar_postgresql()
    if not conn:
        return jsonify([]), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT cnpj, razao_social, nome_fantasia, telefone
            FROM clientes
            WHERE UPPER(razao_social) LIKE UPPER(%s)
               OR UPPER(nome_fantasia) LIKE UPPER(%s)
               OR cnpj LIKE %s
            ORDER BY razao_social
            LIMIT 10
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        clientes = [{
            'cnpj': r[0], 'razao_social': r[1], 'nome_fantasia': r[2], 'telefone': r[3] or ''
        } for r in cur.fetchall()]
        return jsonify(clientes)
    except Exception as e:
        print("Erro ao buscar clientes:", e)
        return jsonify([]), 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@app.route('/api/artigos_produto', methods=['GET'])
def api_artigos_produto():
    conn = conectar_postgresql()
    if not conn:
        return jsonify([]), 500

    cur = None
    try:
        cur = conn.cursor()

        # Tabela normal
        cur.execute("""
            SELECT artigo, codigo, icms_18, icms_12, icms_7, ret_mg
            FROM precos_normal
            ORDER BY artigo
        """)
        artigos_normal = [
            {
                'artigo': row[0],
                'codigo': row[1],
                'precos': {
                    'icms_18': float(row[2]) if row[2] is not None else None,
                    'icms_12': float(row[3]) if row[3] is not None else None,
                    'icms_7':  float(row[4]) if row[4] is not None else None,
                    'ret_mg':  float(row[5]) if row[5] is not None else None,
                },
                'tabela': 'normal'
            }
            for row in cur.fetchall()
        ]

        # Tabela LD
        cur.execute("""
            SELECT artigo, codigo, preco
            FROM precos_ld
            ORDER BY artigo
        """)
        artigos_ld = [
            {
                'artigo': row[0],
                'codigo': row[1],
                'precos': {'ld': float(row[2]) if row[2] is not None else None},
                'tabela': 'ld'
            }
            for row in cur.fetchall()
        ]

        return jsonify(artigos_normal + artigos_ld)

    except Exception as e:
        print('Erro ao buscar artigos:', e)
        return jsonify([]), 500
    finally:
        try:
            if cur:
                cur.close()
            conn.close()
        except:
            pass


def buscar_precos_normal():
    """Busca preços da tabela normal"""
    conn = conectar_postgresql()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg
            FROM precos_normal
            ORDER BY artigo
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"Erro ao buscar preços normal: {e}")
        if conn:
            conn.close()
        return []


@app.route('/api/precos_normal', methods=['GET'])
def api_precos_normal():
    conn = conectar_postgresql()
    if not conn:
        return jsonify([])
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg, observacao FROM precos_normal ORDER BY artigo")
        precos = [{
            'artigo': row[0], 'codigo': row[1], 'descricao': row[2],
            'icms_18': row[3], 'icms_12': row[4], 'icms_7': row[5], 'ret_mg': row[6], 'observacao': row[7]
        } for row in cur.fetchall()]
        return jsonify(precos)
    except Exception as e:
        print(f"Erro ao buscar preços: {e}")
        return jsonify([])
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@app.route('/api/precos_ld', methods=['GET'])
def api_precos_ld():
    conn = conectar_postgresql()
    if not conn:
        return jsonify([])
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT artigo, codigo, preco, observacao FROM precos_ld ORDER BY artigo")
        precos = [{'artigo': row[0], 'codigo': row[1], 'preco': row[2],
                   'observacao': row[3]} for row in cur.fetchall()]
        return jsonify(precos)
    except Exception as e:
        print(f"Erro ao buscar preços LD: {e}")
        return jsonify([])
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@app.route('/precos')
def listar_precos():
    """
    Retorna preços conforme o parâmetro 'tipo':
      - ICMS 7% | ICMS 12% | ICMS 18% | RET (SOMENTE MG): usa buscar_precos_normal()
      - PREÇOS LD (GERAL): lê da tabela precos_ld
    Se 'tipo' não for informado, retorna todas as opções combinadas.
    """
    tipo = request.args.get('tipo', '').strip()

    def buscar_precos_ld():
        conn = conectar_postgresql()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT artigo, codigo, preco, observacao
                FROM precos_ld
                ORDER BY artigo
            """)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows
        except Exception as e:
            print(f"Erro ao buscar preços LD: {e}")
            if conn:
                conn.close()
            return []

    # Mapeamento de coluna de preço por tipo (índices do retorno de buscar_precos_normal)
    col_map_icms = {
        'ICMS 7%': 5,              # icms_7
        'ICMS 12%': 4,             # icms_12
        'ICMS 18%': 3,             # icms_18
        'RET (SOMENTE MG)': 6      # ret_mg
    }

    precos_json = []

    # Caso 1: tipo específico informado
    if tipo:
        # PREÇOS LD (GERAL)
        if 'LD' in tipo.upper():
            ld_rows = buscar_precos_ld()
            for p in ld_rows:
                precos_json.append({
                    'artigo': p[0],
                    'codigo': p[1],
                    'descricao': None,  # tabela LD não possui descrição
                    'preco': float(p[2]) if p[2] is not None else 0.0,
                    'observacao': p[3]
                })
            return jsonify({'precos': precos_json, 'total': len(precos_json)})

        # Demais (ICMS/RET) usando precos_normal
        # [(artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg)]
        normal_rows = buscar_precos_normal()
        col_idx = col_map_icms.get(tipo)
        if col_idx is None:
            # fallback seguro: ICMS 18%
            col_idx = col_map_icms['ICMS 18%']

        for p in normal_rows:
            preco = p[col_idx]
            precos_json.append({
                'artigo': p[0],
                'codigo': p[1],
                'descricao': p[2],
                'preco': float(preco) if preco is not None else 0.0
            })
        return jsonify({'precos': precos_json, 'total': len(precos_json)})

    # Caso 2: sem tipo -> retorna todas as opções combinadas
    normal_rows = buscar_precos_normal()
    ld_rows = buscar_precos_ld()

    # Expandir ICMS/RET em linhas com campo 'tipo'
    for label, idx in col_map_icms.items():
        for p in normal_rows:
            preco = p[idx]
            precos_json.append({
                'tipo': label,
                'artigo': p[0],
                'codigo': p[1],
                'descricao': p[2],
                'preco': float(preco) if preco is not None else 0.0
            })

    # Adicionar LD com 'tipo' apropriado
    for p in ld_rows:
        precos_json.append({
            'tipo': 'PREÇOS LD (GERAL)',
            'artigo': p[0],
            'codigo': p[1],
            'descricao': None,
            'preco': float(p[2]) if p[2] is not None else 0.0
        })

    return jsonify({'precos': precos_json, 'total': len(precos_json)})


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    try:
        dados = request.get_json() or {}
        numero_pedido = salvar_pedido(dados)
        if not numero_pedido:
            return jsonify({'sucesso': False, 'erro': 'Erro ao salvar pedido no banco de dados'})

        pdf_buffer = gerar_pdf_pedido(dados, numero_pedido)
        if not pdf_buffer:
            return jsonify({'sucesso': False, 'erro': 'Erro ao gerar PDF do pedido'})

        enviar_email_pedido_completo(dados, numero_pedido, pdf_buffer)
        return jsonify({'sucesso': True, 'numero_pedido': numero_pedido, 'mensagem': 'Pedido enviado'})
    except Exception as e:
        print(f"❌ Erro no processamento do pedido: {e}")
        return jsonify({'sucesso': False, 'erro': f'Erro interno: {str(e)}'})


@app.route('/baixar-pedido/<numero_pedido>', methods=['GET'])
def baixar_pedido(numero_pedido):
    conn = conectar_postgresql()
    if not conn:
        return "Banco não disponível", 500
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT dados_json FROM pedidos WHERE numero_pedido=%s", (numero_pedido,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return "Pedido não encontrado", 404
        dados_pedido = json.loads(row[0])
        pdf_buffer = gerar_pdf_pedido(dados_pedido, numero_pedido)
        if pdf_buffer is None:
            return "Erro ao gerar PDF", 500
        return send_file(pdf_buffer, as_attachment=True,
                         download_name=f"Pedido_DTX_{numero_pedido}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        print(f"Erro no download: {e}")
        return "Erro inesperado", 500

# Inicialização para produção (Gunicorn)


def create_app():
    """Factory function para produção"""
    ensure_db_initialized()
    return app


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
# Para desenvolvimento local
if __name__ == '__main__':
    host, port, debug = get_port_and_host()
    print(f"🔗 Host: {host}, Porta: {port}, Debug: {debug}")
    ensure_db_initialized()
    app.run(host=host, port=port, debug=debug)

# NÃO chamar ensure_db_initialized() aqui fora!
# O Gunicorn vai usar o app diretamente e o before_request cuida da inicialização
