from flask import Flask, render_template, request, jsonify, send_file
from flask import send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
from datetime import datetime
import json
import socket
import uuid

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
    "À Vista",
    "7 dias",
    "14 dias", 
    "21 dias",
    "28 dias",
    "56 dias",
    "84 dias",
    "56/84 dias",
    "56/84/112 dias",
    "7/14/21 dias",
    "21/28/35 dias",
    "35/42/49 dias",
    "49/56/63 dias",
    "42/49/56/63/70 dias",
    "56/63/70/77/84 dias",
    "84/112/140 dias",
    "56/70/84/98/112 dias"
]

def gerar_numero_pedido():
    """Gerar número único do pedido"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"DTX-{timestamp}"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/buscar_clientes')
def buscar_clientes():
    """API melhorada para buscar clientes com preenchimento automático"""
    query = request.args.get('q', '').strip().lower()
    
    if len(query) < 1:  # Buscar desde o primeiro caractere
        return jsonify([])

    results = []
    # Buscar por CNPJ ou nome
    for cnpj, nome_fantasia in CLIENTES_NOMES.items():
        razao_social = CLIENTES_DATA[cnpj]
        
        # Busca no CNPJ (sem formatação) ou no nome
        cnpj_limpo = cnpj.replace('.', '').replace('/', '').replace('-', '')
        
        if (query in cnpj.lower() or 
            query in cnpj_limpo.lower() or 
            query in nome_fantasia.lower() or 
            query in razao_social.lower()):
            
            results.append({
                'cnpj': cnpj,
                'razao_social': razao_social,
                'nome_fantasia': nome_fantasia,
                'telefone': '11999990000'  # Telefone padrão
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
    """Submissão com validações melhoradas - incluindo RET (SOMENTE MG)"""
    try:
        data = request.get_json()
        print("✅ Pedido Designtex recebido:", json.dumps(data, indent=2, ensure_ascii=False))

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
            'icmsNormal': 'ICMS Normal',
            'icmsLD': 'ICMS LD'
        }
        
        # Verificar campos obrigatórios
        for field, label in required_fields.items():
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{label} é obrigatório'})
        
        # Validar se tem produtos
        produtos = data.get('produtos', [])
        if not produtos:
            return jsonify({'success': False, 'message': 'Adicione pelo menos um produto'})
        
        # Validar cada produto
        for i, produto in enumerate(produtos, 1):
            campos_produto = ['artigo', 'codigo', 'desenho_cor', 'metragem', 'preco']
            for campo in campos_produto:
                if not produto.get(campo):
                    return jsonify({
                        'success': False, 
                        'message': f'Produto {i}: campo "{campo}" é obrigatório'
                    })

        # Validação específica para RET (SOMENTE MG)
        icms_normal = data.get('icmsNormal', '')
        icms_ld = data.get('icmsLD', '')
        regime_ret = data.get('regimeRET', 'Não')
        
        if 'RET' in icms_normal or 'RET' in icms_ld:
            print(f"⚠️  RET selecionado - ICMS Normal: {icms_normal}, ICMS LD: {icms_ld}")
            print(f"⚠️  Regime RET: {regime_ret}")
            # Aqui você pode adicionar validações específicas para MG se necessário

        # Gerar número do pedido
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
                'tipo_frete': data.get('tipoFrete'),
                'transportadora_fob': data.get('transportadoraFOB', ''),
                'transportadora_cif': data.get('transportadoraCIF', ''),
                'venda_triangular': data.get('vendaTriangular', 'Não'),
                'dados_triangulacao': data.get('dadosTriangulacao', ''),
                'regime_ret': data.get('regimeRET', 'Não'),  # Sim/Não
                'tipo_produto': data.get('tipoProduto')
            },
            'tabela_precos': {
                'icms_normal': data.get('icmsNormal'),  # Pode ser "RET (SOMENTE MG)"
                'icms_ld': data.get('icmsLD')          # Pode ser "RET LD (SOMENTE MG)"
            },
            'produtos': data.get('produtos', []),
            'valor_total': float(data.get('valorTotal', 0)),
            'observacoes': data.get('observacoes', ''),
            'arquivo_gerado': filename
        }

        # Salvar arquivo JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(pedido_completo, f, ensure_ascii=False, indent=2)

        print(f"📁 Pedido {numero_pedido} salvo em: {filepath}")

        # Gerar PDF automaticamente
        pdf_filename = filename.replace('.json', '.pdf')
        pdf_path = os.path.join('uploads', pdf_filename)
        gerar_pdf_pedido(pedido_completo, pdf_path)

        return jsonify({
            'success': True,
            'message': f'Pedido {numero_pedido} enviado com sucesso! Email com PDF será enviado via EmailJS.',
            'numero_pedido': numero_pedido,
            'timestamp': pedido_completo['timestamp'],
            'arquivo': filename,
            'pdf': pdf_filename,
            'valor_total': pedido_completo['valor_total']
        })

    except Exception as e:
        print(f"❌ Erro ao processar pedido: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

def gerar_pdf_pedido(dados, pdf_path):
    """Gerar PDF melhorado com R.E.T (SOMENTE MG)"""
    try:
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                              rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        story = []

        # Título melhorado
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=20,
            spaceAfter=30,
            alignment=1,  # Centro
            textColor=colors.HexColor('#1a5490')
        )
        
        # Título com número do pedido
        story.append(Paragraph(
            f"🏭 PEDIDO DE VENDAS DESIGNTEX<br/>N° <b>{dados.get('numero_pedido', 'N/A')}</b>", 
            title_style))
        story.append(Spacer(1, 20))

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

        # Dados do corpo - COM R.E.T (SOMENTE MG)
        story.append(Paragraph("<b>CONDIÇÕES DO PEDIDO</b>", styles['Heading2']))
        
        # Formatar regime RET no PDF
        regime_ret_display = dados['dados_corpo']['regime_ret']
        if regime_ret_display == 'Sim':
            regime_ret_display = 'Sim (Somente MG)'
        
        corpo_data = [
            ['Prazo Pagamento:', dados['dados_corpo']['prazo_pagamento']],
            ['Tipo Pedido:', dados['dados_corpo']['tipo_pedido']],
            ['Tipo Frete:', dados['dados_corpo']['tipo_frete']],
            ['Venda Triangular:', dados['dados_corpo']['venda_triangular']],
            ['Regime R.E.T:', regime_ret_display],  # Aqui mostra (Somente MG) se for Sim
            ['Tipo Produto:', dados['dados_corpo']['tipo_produto']],
            ['ICMS Normal:', dados['tabela_precos']['icms_normal']],     # Pode ser "RET (SOMENTE MG)"
            ['ICMS LD:', dados['tabela_precos']['icms_ld']]            # Pode ser "RET LD (SOMENTE MG)"
        ]

        # Adicionar transportadoras se preenchidas
        if dados['dados_corpo']['transportadora_fob']:
            corpo_data.append(['Transportadora FOB:', dados['dados_corpo']['transportadora_fob']])
        if dados['dados_corpo']['transportadora_cif']:
            corpo_data.append(['Transportadora CIF:', dados['dados_corpo']['transportadora_cif']])
        if dados['dados_corpo']['dados_triangulacao']:
            corpo_data.append(['Dados Triangulação:', dados['dados_corpo']['dados_triangulacao']])

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
            story.append(Paragraph("<b>PRODUTOS SOLICITADOS</b>", styles['Heading2']))
            produtos_data = [['Item', 'Artigo', 'Código', 'Desenho/Cor', 'Metragem', 'Preço/m', 'Subtotal']]

            for i, produto in enumerate(dados['produtos'], 1):
                # Limitar caracteres para não quebrar layout
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

            # Linha do total
            produtos_data.append([
                '', '', '', '', '', '<b>TOTAL GERAL:</b>', 
                f"<b>R$ {dados['valor_total']:.2f}</b>".replace('.', ',')
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
                ('BACKGROUND', (-2, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Linhas alternadas
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.lightgrey])
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

        # Rodapé informativo sobre RET
        rodape_style = ParagraphStyle(
            'RodapeStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1,
            textColor=colors.grey
        )
        story.append(Spacer(1, 20))
        
        # Adicionar nota sobre RET se aplicável
        tem_ret = False
        if 'RET' in dados['tabela_precos']['icms_normal'] or 'RET' in dados['tabela_precos']['icms_ld'] or dados['dados_corpo']['regime_ret'] == 'Sim':
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
                "<b>⚠️  ATENÇÃO: R.E.T (Regime Especial Tributário) - VÁLIDO SOMENTE PARA MINAS GERAIS</b>", 
                nota_ret))
            story.append(Spacer(1, 10))
        
        story.append(Paragraph(
            f"Pedido gerado automaticamente pelo sistema Designtex Tecidos em {dados['timestamp']}", 
            rodape_style))

        # Gerar PDF
        doc.build(story)
        print(f"✅ PDF melhorado gerado: {pdf_path}")
        
        if tem_ret:
            print(f"⚠️  PDF contém informações de R.E.T (SOMENTE MG)")

    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {str(e)}")
        # Fallback para o PDF original em caso de erro
        try:
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            story.append(Paragraph("PEDIDO DE VENDAS DESIGNTEX TECIDOS", styles['Title']))
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"Número: {dados.get('numero_pedido', 'N/A')}", styles['Normal']))
            story.append(Paragraph(f"Data: {dados['timestamp']}", styles['Normal']))
            story.append(Paragraph(f"Representante: {dados['dados_cabecalho']['representante']}", styles['Normal']))
            story.append(Paragraph(f"Cliente: {dados['dados_cabecalho']['razao_social']}", styles['Normal']))
            story.append(Paragraph(f"Total: R$ {dados['valor_total']:.2f}".replace('.', ','), styles['Normal']))
            
            doc.build(story)
            print(f"✅ PDF simples gerado como fallback: {pdf_path}")
        except Exception as e2:
            print(f"❌ Erro também no PDF simples: {str(e2)}")
            raise e2

@app.route('/gerar_pdf/<filename>')
def gerar_pdf(filename):
    """Download do PDF do pedido"""
    try:
        pdf_filename = filename.replace('.json', '.pdf')
        pdf_path = os.path.join('uploads', pdf_filename)

        if os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)
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
        'versao': '2.1 - RET (Somente MG)',
        'recursos': [
            'Autocomplete de clientes',
            'Validação RET para MG',
            'PDF com alertas RET',
            'Numeração única de pedidos'
        ]
    })

if __name__ == '__main__':
    # Criar pasta uploads se não existir
    os.makedirs('uploads', exist_ok=True)
    
    # Criar pasta static se não existir
    os.makedirs('static', exist_ok=True)

    # Descobrir IP automaticamente
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    print("🚀 Iniciando DESIGNTEX TECIDOS - Versão R.E.T (Somente MG)")
    print("=" * 70)
    print("📱 PC: http://localhost:5001")
    print(f"🌐 CELULAR: http://{local_ip}:5001")
    print("📧 Email: PDF em anexo via EmailJS")
    print("🏭 Empresa: Designtex Tecidos")
    print("⚠️  R.E.T: Válido somente para Minas Gerais")
    print("✅ Health Check: /health")
    print("🔍 Busca Clientes: /api/buscar_clientes")
    print("=" * 70)

    # Desabilitar debug para evitar erros de debugger
    app.run(debug=False, host='0.0.0.0', port=5001)
