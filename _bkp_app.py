from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
from datetime import datetime
import json
import socket

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
    "7/14/21 dias",           # A: Inicia 7º, finaliza 21º
    "21/28/35 dias",          # B: Inicia 21º, finaliza 35º
    "35/42/49 dias",          # C: Inicia 35º, finaliza 49º
    "49/56/63 dias",          # D: Inicia 49º, finaliza 63º
    "42/49/56/63/70 dias",    # E: Inicia 42º, finaliza 70º
    "56/63/70/77/84 dias",    # F: Inicia 56º, finaliza 84º
    "84/112/140 dias",        # G: Inicia 84º, finaliza 140º
    "56/70/84/98/112 dias"    # H: Inicia 56º, finaliza 112º
]


@app.route('/')
def index():
    return render_template('index.html',
                           clientes=CLIENTES_DATA,
                           prazos=PRAZOS_PAGAMENTO)


@app.route('/submit_pedido', methods=['POST'])
def submit_pedido():
    try:
        data = request.get_json()
        print("✅ Pedido recebido:", json.dumps(
            data, indent=2, ensure_ascii=False))

        # Validações básicas
        if not data.get('nomeRepresentante'):
            return jsonify({'success': False, 'message': 'Nome do representante é obrigatório'})

        if not data.get('razaoSocial'):
            return jsonify({'success': False, 'message': 'Razão Social é obrigatória'})

        # Salvar pedido em arquivo JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'pedido_designtex_{timestamp}.json'
        filepath = os.path.join('uploads', filename)

        # Dados completos do pedido
        pedido_completo = {
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
                'transportadora_fob': data.get('transportadoraFOB'),
                'transportadora_cif': data.get('transportadoraCIF'),
                'venda_triangular': data.get('vendaTriangular'),
                'dados_triangulacao': data.get('dadosTriangulacao'),
                'regime_ret': data.get('regimeRET'),
                'tipo_produto': data.get('tipoProduto')
            },
            'tabela_precos': {
                'icms_normal': data.get('icmsNormal'),
                'icms_ld': data.get('icmsLD')
            },
            'produtos': data.get('produtos', []),
            'valor_total': data.get('valorTotal', 0),
            'observacoes': data.get('observacoes', ''),
            'arquivo_gerado': filename
        }

        # Salvar arquivo JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(pedido_completo, f, ensure_ascii=False, indent=2)

        print(f"📁 Pedido Designtex salvo em: {filepath}")

        # Gerar PDF automaticamente
        pdf_filename = filename.replace('.json', '.pdf')
        pdf_path = os.path.join('uploads', pdf_filename)
        gerar_pdf_pedido(pedido_completo, pdf_path)

        return jsonify({
            'success': True,
            'message': f'Pedido Designtex salvo com sucesso! Email será enviado via EmailJS.',
            'timestamp': pedido_completo['timestamp'],
            'arquivo': filename,
            'pdf': pdf_filename,
            'valor_total': pedido_completo['valor_total']
        })

    except Exception as e:
        print(f"❌ Erro ao processar pedido: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})


def gerar_pdf_pedido(dados, pdf_path):
    """Gerar PDF do pedido Designtex"""
    try:
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Centro
        )
        story.append(
            Paragraph("🏭 PEDIDO DE VENDAS DESIGNTEX TECIDOS", title_style))
        story.append(Spacer(1, 20))

        # Dados do cabeçalho
        story.append(Paragraph("<b>DADOS DO CLIENTE</b>", styles['Heading2']))
        cabecalho_data = [
            ['Representante:', dados['dados_cabecalho']['representante']],
            ['Razão Social:', dados['dados_cabecalho']['razao_social']],
            ['CNPJ:', dados['dados_cabecalho']['cnpj']],
            ['Telefone:', dados['dados_cabecalho']['telefone']],
            ['Data:', dados['timestamp']],
            ['Empresa:', 'Designtex Tecidos']
        ]

        cabecalho_table = Table(cabecalho_data, colWidths=[2*inch, 4*inch])
        cabecalho_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(cabecalho_table)
        story.append(Spacer(1, 20))

        # Dados do corpo
        story.append(Paragraph("<b>DADOS DO PEDIDO</b>", styles['Heading2']))
        corpo_data = [
            ['Prazo Pagamento:', dados['dados_corpo']['prazo_pagamento']],
            ['Tipo Pedido:', dados['dados_corpo']['tipo_pedido']],
            ['Tipo Frete:', dados['dados_corpo']['tipo_frete']],
            ['Venda Triangular:', dados['dados_corpo']['venda_triangular']],
            ['Regime RET:', dados['dados_corpo']['regime_ret']],
            ['Tipo Produto:', dados['dados_corpo']['tipo_produto']]
        ]

        corpo_table = Table(corpo_data, colWidths=[2*inch, 4*inch])
        corpo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(corpo_table)
        story.append(Spacer(1, 20))

        # Produtos
        if dados['produtos']:
            story.append(Paragraph("<b>PRODUTOS</b>", styles['Heading2']))
            produtos_data = [['Artigo', 'Código',
                              'Desenho/Cor', 'Metragem', 'Preço/m', 'Total']]

            for produto in dados['produtos']:
                produtos_data.append([
                    produto['artigo'],
                    produto['codigo'],
                    produto['desenho_cor'],
                    f"{produto['metragem']}m",
                    f"R$ {produto['preco']:.2f}".replace('.', ','),
                    f"R$ {produto['subtotal']:.2f}".replace('.', ',')
                ])

            # Linha do total
            produtos_data.append(
                ['', '', '', '', 'TOTAL GERAL:', f"R$ {dados['valor_total']:.2f}".replace('.', ',')])

            produtos_table = Table(produtos_data, colWidths=[
                                   1.5*inch, 1*inch, 1.5*inch, 1*inch, 1*inch, 1*inch])
            produtos_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (-2, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(produtos_table)
            story.append(Spacer(1, 20))

        # Observações
        if dados['observacoes']:
            story.append(Paragraph("<b>OBSERVAÇÕES</b>", styles['Heading2']))
            story.append(Paragraph(dados['observacoes'], styles['Normal']))

        # Gerar PDF
        doc.build(story)
        print(f"✅ PDF Designtex gerado: {pdf_path}")

    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {str(e)}")


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


if __name__ == '__main__':
    # Criar pasta uploads se não existir
    os.makedirs('uploads', exist_ok=True)

    # Descobrir IP automaticamente
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("🚀 Iniciando sistema DESIGNTEX TECIDOS com EmailJS + Outlook...")
    print("📱 PC: http://localhost:5000")
    print(f"🌐 CELULAR: http://{local_ip}:5000")
    print("📧 Email: Outlook via EmailJS configurado")
    print("🏭 Empresa: Designtex Tecidos")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=5000)
