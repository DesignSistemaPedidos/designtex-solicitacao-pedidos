from flask import Flask, render_template, request, jsonify, send_file
from flask import send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
import sqlite3
from datetime import datetime
import json
import socket
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

app = Flask(__name__)
app.secret_key = 'designtex-vendas-emailjs-2024'

# DADOS DOS CLIENTES - CNPJ como chave primária
CLIENTES_DATA = {
    "12.345.678/0001-90": "EMPRESA ABC LTDA",
    "98.765.432/0001-10": "COMERCIAL XYZ S/A",
    "11.222.333/0001-44": "DISTRIBUIDORA 123 LTDA",
    "55.666.777/0001-88": "CONFECÇÕES DELTA LTDA",
    "33.444.555/0001-66": "INDÚSTRIA BETA LTDA",
    "77.888.999/0001-22": "TÊXTIL GAMMA S/A"
}

# Para autocomplete - primeiros nomes das empresas
CLIENTES_NOMES = {
    "12.345.678/0001-90": "EMPRESA ABC",
    "98.765.432/0001-10": "COMERCIAL XYZ",
    "11.222.333/0001-44": "DISTRIBUIDORA 123",
    "55.666.777/0001-88": "CONFECÇÕES DELTA",
    "33.444.555/0001-66": "INDÚSTRIA BETA",
    "77.888.999/0001-22": "TÊXTIL GAMMA"
}

# PRAZOS ATUALIZADOS COMPLETOS
PRAZOS_PAGAMENTO = [
    "À Vista", "7 dias", "14 dias", "21 dias", "28 dias", "56 dias", "84 dias",
    "56/84 dias", "56/84/112 dias", "7/14/21 dias", "21/28/35 dias",
    "35/42/49 dias", "49/56/63 dias", "42/49/56/63/70 dias",
    "56/63/70/77/84 dias", "84/112/140 dias", "56/70/84/98/112 dias"
]

# CONFIGURAÇÕES DE EMAIL
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',  # ou seu provedor
    'smtp_port': 587,
    'email': 'design.designtextecidos@gmail.com',  # Configure aqui
    'password': 'kmqq xayd plif mrgb',     # Configure aqui
    'destinatario': 'pedido@designtextecidos.com.br'
}


def init_db():
    """Inicializar banco SQLite para numeração sequencial"""
    conn = sqlite3.connect('designtex.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pedidos_sequencia (
            data TEXT PRIMARY KEY,
            ultimo_numero INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def gerar_numero_pedido():
    """Gerar número sequencial simples 0001, 0002, ..., 9999, 10000"""
    conn = sqlite3.connect('designtex.db')
    cursor = conn.cursor()

    # Buscar último número geral (sem data)
    cursor.execute(
        'SELECT ultimo_numero FROM pedidos_sequencia WHERE data = "GERAL"')
    resultado = cursor.fetchone()

    if resultado:
        proximo_numero = resultado[0] + 1
        cursor.execute('UPDATE pedidos_sequencia SET ultimo_numero = ? WHERE data = "GERAL"',
                       (proximo_numero,))
    else:
        proximo_numero = 1
        cursor.execute('INSERT INTO pedidos_sequencia (data, ultimo_numero) VALUES ("GERAL", ?)',
                       (proximo_numero,))

    conn.commit()
    conn.close()

    # Formato: 0001, 0002, ..., 9999, 10000, 10001...
    if proximo_numero <= 9999:
        return f"{proximo_numero:04d}"  # 0001, 0002, ..., 9999
    else:
        return str(proximo_numero)      # 10000, 10001, 10002...


def enviar_email_pedido(dados_pedido, pdf_path):
    """Enviar pedido por email com PDF em anexo"""
    try:
        # Configurar email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = EMAIL_CONFIG['destinatario']
        msg['Subject'] = f"Pedido Designtex - {dados_pedido['numero_pedido']} - {dados_pedido['dados_cabecalho']['representante']}"

        # Corpo do email
        corpo_email = f"""
        <html>
        <body>
            <h2>🏭 Novo Pedido Designtex Tecidos</h2>
            
            <h3>📋 Dados do Pedido:</h3>
            <ul>
                <li><strong>Número:</strong> {dados_pedido['numero_pedido']}</li>
                <li><strong>Data/Hora:</strong> {dados_pedido['timestamp']}</li>
                <li><strong>Representante:</strong> {dados_pedido['dados_cabecalho']['representante']}</li>
                <li><strong>Cliente:</strong> {dados_pedido['dados_cabecalho']['razao_social']}</li>
                <li><strong>CNPJ:</strong> {dados_pedido['dados_cabecalho']['cnpj']}</li>
                <li><strong>Telefone:</strong> {dados_pedido['dados_cabecalho']['telefone']}</li>
            </ul>
            
            <h3>💰 Resumo Financeiro:</h3>
            <ul>
                <li><strong>Valor Total:</strong> R$ {dados_pedido['valor_total']:.2f}</li>
                <li><strong>Prazo Pagamento:</strong> {dados_pedido['dados_corpo']['prazo_pagamento']}</li>
                <li><strong>Tipo Frete:</strong> {dados_pedido['dados_corpo']['tipo_frete']}</li>
            </ul>
            
            <h3>📦 Produtos:</h3>
            <ul>
        """

        for i, produto in enumerate(dados_pedido['produtos'], 1):
            corpo_email += f"""
                <li><strong>Item {i}:</strong> {produto['artigo']} - {produto['codigo']} 
                    ({produto['metragem']}m x R$ {produto['preco']:.2f} = R$ {produto['subtotal']:.2f})</li>
            """

        corpo_email += f"""
            </ul>
            
            <h3>📝 Observações:</h3>
            <p>{dados_pedido['observacoes'] or 'Nenhuma observação'}</p>
            
            <hr>
            <p><em>Pedido gerado automaticamente pelo sistema Designtex Tecidos</em></p>
            <p><strong>PDF detalhado em anexo.</strong></p>
        </body>
        </html>
        """

        msg.attach(MIMEText(corpo_email, 'html'))

        # Anexar PDF
        with open(pdf_path, "rb") as arquivo:
            anexo = MIMEApplication(arquivo.read(), _subtype="pdf")
            anexo.add_header('Content-Disposition', 'attachment',
                             filename=f'Pedido_{dados_pedido["numero_pedido"]}.pdf')
            msg.attach(anexo)

        # Enviar email
        servidor = smtplib.SMTP(
            EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        servidor.starttls()
        servidor.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        servidor.send_message(msg)
        servidor.quit()

        print(
            f"✅ Email enviado com sucesso para {EMAIL_CONFIG['destinatario']}")
        return True

    except Exception as e:
        print(f"❌ Erro ao enviar email: {str(e)}")
        return False


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/api/buscar_clientes')
def buscar_clientes():
    """API melhorada para buscar clientes com preenchimento automático"""
    query = request.args.get('q', '').strip().lower()

    if len(query) < 1:
        return jsonify([])

    results = []
    for cnpj, nome_fantasia in CLIENTES_NOMES.items():
        razao_social = CLIENTES_DATA[cnpj]
        cnpj_limpo = cnpj.replace('.', '').replace('/', '').replace('-', '')

        if (query in cnpj.lower() or query in cnpj_limpo.lower() or
                query in nome_fantasia.lower() or query in razao_social.lower()):

            results.append({
                'cnpj': cnpj,
                'razao_social': razao_social,
                'nome_fantasia': nome_fantasia,
                'telefone': '11999990000'
            })

    return jsonify(results)


@app.route('/')
def index():
    return render_template('index.html',
                           clientes=CLIENTES_DATA,
                           clientes_nomes=CLIENTES_NOMES,
                           prazos=PRAZOS_PAGAMENTO)


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    """Submissão com validação de ICMS e campo OP"""
    try:
        data = request.get_json()
        print("✅ Pedido Designtex recebido:", json.dumps(
            data, indent=2, ensure_ascii=False))

        # Validações obrigatórias
        required_fields = {
            'nomeRepresentante': 'Nome do representante',
            'razaoSocial': 'Razão Social',
            'cnpj': 'CNPJ',
            'telefone': 'Telefone',
            'prazoPagamento': 'Prazo de pagamento',
            'tipoPedido': 'Tipo de pedido',
            'tipoFrete': 'Tipo de frete',
            'tipoProduto': 'Tipo de produto',
            'tabelaPrecos': 'Tabela de Preços (ICMS Normal ou ICMS LD)'
        }

        for field, label in required_fields.items():
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{label} é obrigatório'})

        # Validação específica: se tipo de pedido é OP, número da OP é obrigatório
        if data.get('tipoPedido') == 'OP' and not data.get('numeroOP'):
            return jsonify({'success': False, 'message': 'Número da OP é obrigatório quando tipo de pedido é OP'})

        produtos = data.get('produtos', [])
        if not produtos:
            return jsonify({'success': False, 'message': 'Adicione pelo menos um produto'})

        for i, produto in enumerate(produtos, 1):
            campos_produto = ['artigo', 'codigo',
                              'desenho_cor', 'metragem', 'preco']
            for campo in campos_produto:
                if not produto.get(campo):
                    return jsonify({
                        'success': False,
                        'message': f'Produto {i}: campo "{campo}" é obrigatório'
                    })

        # Gerar número do pedido SEQUENCIAL
        numero_pedido = gerar_numero_pedido()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'pedido_designtex_{numero_pedido}_{timestamp}.json'
        filepath = os.path.join('uploads', filename)

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
                'numero_op': data.get('numeroOP', ''),  # NOVO: número da OP
                'tipo_frete': data.get('tipoFrete'),
                'transportadora_fob': data.get('transportadoraFOB', ''),
                'transportadora_cif': data.get('transportadoraCIF', ''),
                'venda_triangular': data.get('vendaTriangular', 'Não'),
                'dados_triangulacao': data.get('dadosTriangulacao', ''),
                'regime_ret': data.get('regimeRET', 'Não'),
                'tipo_produto': data.get('tipoProduto')
            },
            'tabela_precos': {
                # NOVO: ICMS Normal ou ICMS LD
                'tipo_tabela': data.get('tabelaPrecos')
            },
            'produtos': data.get('produtos', []),
            'valor_total': float(data.get('valorTotal', 0)),
            'observacoes': data.get('observacoes', ''),
            'arquivo_gerado': filename
        }

        # Salvar arquivo JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(pedido_completo, f, ensure_ascii=False, indent=2)

        # Gerar PDF
        pdf_filename = filename.replace('.json', '.pdf')
        pdf_path = os.path.join('uploads', pdf_filename)
        gerar_pdf_pedido(pedido_completo, pdf_path)

        # Enviar email
        email_enviado = enviar_email_pedido(pedido_completo, pdf_path)

        print(f"📁 Pedido {numero_pedido} processado com sucesso!")

        return jsonify({
            'success': True,
            'message': f'Pedido {numero_pedido} enviado com sucesso!',
            'numero_pedido': numero_pedido,
            'timestamp': pedido_completo['timestamp'],
            'arquivo': filename,
            'pdf': pdf_filename,
            'pdf_url': f'/download_pdf/{pdf_filename}',
            'valor_total': pedido_completo['valor_total'],
            'email_enviado': email_enviado
        })

    except Exception as e:
        print(f"❌ Erro ao processar pedido: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})


def gerar_pdf_pedido(dados, pdf_path):
    """Gerar PDF com correções de formatação"""
    try:
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        story = []

        # ADICIONAR LOGO (se existir)
        logo_path = os.path.join('static', 'logo_designtex.png')
        if os.path.exists(logo_path):
            try:
                logo = Image(logo_path, width=2*inch, height=1*inch)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 20))
            except:
                print("⚠️  Erro ao carregar logo, continuando sem logo")

        # Título melhorado
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=20,
            spaceAfter=30,
            alignment=1,  # Centro
            textColor=colors.HexColor('#1a5490')
        )

        story.append(Paragraph(
            f"🏭 PEDIDO DE VENDAS DESIGNTEX<br/>N° <b>{dados.get('numero_pedido', 'N/A')}</b>",
            title_style))

        # Dados do cabeçalho
        story.append(Paragraph("<b>DADOS DO CLIENTE</b>", styles['Heading2']))
        cabecalho_data = [
            ['Representante:', dados['dados_cabecalho']['representante']],
            ['CNPJ:', dados['dados_cabecalho']['cnpj']],
            ['Razão Social:', dados['dados_cabecalho']['razao_social']],
            ['Telefone:', dados['dados_cabecalho']['telefone']],
            ['Data/Hora:', dados['timestamp']],
            ['Empresa:', 'Designtex Tecidos']
        ]

        cabecalho_table = Table(cabecalho_data, colWidths=[2*inch, 4*inch])
        cabecalho_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey)
        ]))
        story.append(cabecalho_table)
        story.append(Spacer(1, 20))

        # Dados do corpo - COM correções
        story.append(
            Paragraph("<b>CONDIÇÕES DO PEDIDO</b>", styles['Heading2']))

        regime_ret_display = dados['dados_corpo']['regime_ret']
        if regime_ret_display == 'Sim':
            regime_ret_display = 'Sim (Somente MG)'

        corpo_data = [
            ['Prazo Pagamento:', dados['dados_corpo']['prazo_pagamento']],
            ['Tipo Pedido:', dados['dados_corpo']['tipo_pedido']],
            ['Tipo Frete:', dados['dados_corpo']['tipo_frete']],
            ['Venda Triangular:', dados['dados_corpo']['venda_triangular']],
            ['Regime R.E.T:', regime_ret_display],
            ['Tipo Produto:', dados['dados_corpo']['tipo_produto']],
            # CORRIGIDO: só mostra o tipo selecionado
            ['Tabela de Preços:', dados['tabela_precos']['tipo_tabela']]
        ]

        # NOVO: Adicionar número da OP se for tipo OP
        if dados['dados_corpo']['tipo_pedido'] == 'OP' and dados['dados_corpo']['numero_op']:
            corpo_data.insert(
                2, ['Número da OP:', dados['dados_corpo']['numero_op']])

        if dados['dados_corpo']['transportadora_fob']:
            corpo_data.append(
                ['Transportadora FOB:', dados['dados_corpo']['transportadora_fob']])
        if dados['dados_corpo']['transportadora_cif']:
            corpo_data.append(
                ['Transportadora CIF:', dados['dados_corpo']['transportadora_cif']])
        if dados['dados_corpo']['dados_triangulacao']:
            corpo_data.append(
                ['Dados Triangulação:', dados['dados_corpo']['dados_triangulacao']])

        corpo_table = Table(corpo_data, colWidths=[2*inch, 4*inch])
        corpo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey)
        ]))
        story.append(corpo_table)
        story.append(Spacer(1, 20))

        # Produtos
        if dados['produtos']:
            story.append(
                Paragraph("<b>PRODUTOS SOLICITADOS</b>", styles['Heading2']))
            produtos_data = [['Item', 'Artigo', 'Código',
                              'Desenho/Cor', 'Metragem', 'Preço/m', 'Subtotal']]

            for i, produto in enumerate(dados['produtos'], 1):
                artigo = str(produto['artigo'])[:25]
                codigo = str(produto['codigo'])[:15]
                desenho_cor = str(produto['desenho_cor'])[:20]

                produtos_data.append([
                    str(i),
                    artigo,
                    codigo,
                    desenho_cor,
                    f"{produto['metragem']}m",
                    f"R$ {produto['preco']:.2f}".replace('.', ','),
                    f"R$ {produto['subtotal']:.2f}".replace('.', ',')
                ])

            # CORRIGIDO: Linha do total sem tags HTML
            produtos_data.append([
                '', '', '', '', '', 'TOTAL GERAL:',
                f"R$ {dados['valor_total']:.2f}".replace('.', ',')
            ])

            produtos_table = Table(produtos_data, colWidths=[
                0.4*inch, 1.4*inch, 0.9*inch, 1.3*inch, 0.8*inch, 0.9*inch, 1*inch
            ])
            produtos_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                # CORRIGIDO: Estilo da linha do total sem HTML
                ('BACKGROUND', (-2, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (-2, -1), (-1, -1), 10),
                ('TEXTCOLOR', (-2, -1), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2),
                 [colors.white, colors.lightgrey])
            ]))
            story.append(produtos_table)
            story.append(Spacer(1, 20))

        # Observações
        if dados['observacoes']:
            story.append(Paragraph("<b>OBSERVAÇÕES</b>", styles['Heading2']))
            obs_style = ParagraphStyle(
                'ObsStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                leftIndent=10,
                rightIndent=10,
                borderWidth=1,
                borderColor=colors.grey,
                borderPadding=10
            )
            story.append(Paragraph(dados['observacoes'], obs_style))
            story.append(Spacer(1, 20))

        # Alerta RET se necessário
        tem_ret = False
        tabela_precos = dados['tabela_precos']['tipo_tabela']
        if ('RET' in tabela_precos or dados['dados_corpo']['regime_ret'] == 'Sim'):
            tem_ret = True
            nota_ret = ParagraphStyle(
                'NotaRET',
                parent=styles['Normal'],
                fontSize=9,
                alignment=1,
                textColor=colors.red,
                borderWidth=1,
                borderColor=colors.red,
                borderPadding=8
            )
            story.append(Paragraph(
                "⚠️  ATENÇÃO: R.E.T (Regime Especial Tributário) - VÁLIDO SOMENTE PARA MINAS GERAIS",
                nota_ret))
            story.append(Spacer(1, 10))

        # Rodapé
        rodape_style = ParagraphStyle(
            'RodapeStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1,
            textColor=colors.grey
        )
        story.append(Paragraph(
            f"Pedido gerado automaticamente pelo sistema Designtex Tecidos em {dados['timestamp']}",
            rodape_style))

        doc.build(story)
        print(f"✅ PDF gerado: {pdf_path}")

    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {str(e)}")
        raise e


@app.route('/download_pdf/<filename>')
def download_pdf(filename):
    """Rota para download direto do PDF"""
    try:
        pdf_path = os.path.join('uploads', filename)
        if os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'success': False, 'message': 'PDF não encontrado'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao baixar PDF: {str(e)}'})


@app.route('/health')
def health_check():
    """Endpoint para verificar se o sistema está funcionando"""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        'empresa': 'Designtex Tecidos',
        'versao': '2.4 - Numeração Sequencial Simples',
        'recursos': [
            'Seleção única ICMS Normal OU ICMS LD',
            'Campo Número da OP para tipo OP',
            'PDF formatação corrigida',
            'Numeração sequencial DTX-AAAAMMDD-0001',
            'Email + Download automático'
        ]
    })


if __name__ == '__main__':
    # Criar pastas necessárias
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    # Inicializar banco para numeração
    init_db()

    # Descobrir IP automaticamente
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    print("🚀 Iniciando DESIGNTEX TECIDOS - Versão Corrigida")
    print("=" * 70)
    print("📱 PC: http://localhost:5001")
    print(f"🌐 CELULAR: http://{local_ip}:5001")
    print("📧 Email: Automático para pedido@designtextecidos.com.br")
    print("💾 Download: PDF automático após envio")
    print("🔢 Numeração: 0001, 0002, ..., 9999, 10000 (sequencial)")
    print("📊 ICMS: Seleção única (Normal OU LD)")
    print("📝 OP: Campo obrigatório para tipo OP")
    print("=" * 70)

    app.run(debug=False, host='0.0.0.0', port=5001)
