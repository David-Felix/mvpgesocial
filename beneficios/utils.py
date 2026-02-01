import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from datetime import datetime
from num2words import num2words

def valor_por_extenso(valor):
    """Converte valor para extenso"""
    try:
        # Separa reais e centavos
        reais = int(valor)
        centavos = int((valor - reais) * 100)
        
        extenso_reais = num2words(reais, lang='pt_BR')
        
        if centavos > 0:
            extenso_centavos = num2words(centavos, lang='pt_BR')
            if reais == 1:
                return f"{extenso_reais} real e {extenso_centavos} centavos"
            else:
                return f"{extenso_reais} reais e {extenso_centavos} centavos"
        else:
            if reais == 1:
                return f"{extenso_reais} real"
            else:
                return f"{extenso_reais} reais"
    except:
        return f"{valor:.2f} reais"

def desenhar_conteudo_recibo(c, pessoa, width, height, margin):
    """Função auxiliar para desenhar o conteúdo do recibo com cabeçalho oficial"""
    
    # --- Cabeçalho Oficial ---
    y_header = height - 3.5 * cm
    
    # 1. Brasão (Tenta carregar se existir)
    # Altere o caminho abaixo para o local real da imagem no seu servidor
    caminho_brasao = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'brasao.jpg')
    if os.path.exists(caminho_brasao):
        c.drawImage(caminho_brasao, (width/2) - 1.0*cm, y_header, width=1.5*cm, height=1.5*cm, mask='auto')
        y_header -= 1.5 * cm
    else:
        # Se não houver imagem, apenas pula o espaço
        y_header -= 1.5 * cm
        
    # 2. Textos do Cabeçalho
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, y_header, "ESTADO DA PARAÍBA")
    y_header -= 0.5 * cm
    c.drawCentredString(width / 2, y_header, "PREFEITURA MUNICIPAL DE POCINHOS")
    y_header -= 0.5 * cm
    c.drawCentredString(width / 2, y_header, "SECRETARIA MUNICIPAL DE ASSISTÊNCIA DE SOCIAL")
    
    # --- Título "RECIBO" ---
    y_recibo = y_header - 2.5 * cm
    c.setFont("Helvetica-Bold", 25)
    c.drawCentredString(width / 2, y_recibo, "R E C I B O")
    
    # --- Valor ---
    c.setFont("Helvetica-Bold", 11)
    valor_formatado = f"{pessoa.valor_beneficio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    c.drawRightString(width - margin, y_recibo - 2 * cm, f"Valor R$ {valor_formatado}")
    
    # --- Configuração do Texto Justificado com Parágrafo ---
    styles = getSampleStyleSheet()
    style_justificado = ParagraphStyle(
        'CustomJustify',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=18,
        alignment=TA_JUSTIFY,
        firstLineIndent=2 * cm
    )
    
    meses = [
        "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
        "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
    ]
    mes_nome = meses[datetime.now().month - 1]
    valor_ext = valor_por_extenso(pessoa.valor_beneficio).upper()
    
    nome_beneficio = pessoa.beneficio.nome if hasattr(pessoa, 'beneficio') else 'Auxílio'
    texto_html = (
        f"Recebi da Prefeitura Municipal de Pocinhos, a importância de "
        f"<b>R$ {valor_formatado} ({valor_ext})</b>, em virtude da necessidade de que "
        f"seja garantido o pagamento referente ao {nome_beneficio}, "
        f"conforme PARECER SOCIAL FAVORÁVEL da Assistente Social do CRAS, "
        f"referente ao mês de <b>{mes_nome}</b> do corrente ano."
    )
    
    p1 = Paragraph(texto_html, style_justificado)
    largura_util = width - (2 * margin)
    w, h = p1.wrap(largura_util, height)
    y_pos = y_recibo - 4 * cm - h
    p1.drawOn(c, margin, y_pos)
    
    texto_quitacao = "Pelo que emito o presente recibo em duas vias de igual teor, dando-lhe plena e total quitação."
    p2 = Paragraph(texto_quitacao, style_justificado)
    w2, h2 = p2.wrap(largura_util, height)
    y_pos = y_pos - h2 - 0.5 * cm
    p2.drawOn(c, margin, y_pos)
    
    # --- Local e Data ---
    y_pos -= 2 * cm
    c.setFont("Helvetica", 12)
    ano_atual = datetime.now().year
    c.drawRightString(width - margin, y_pos, f"Pocinhos, _______/_______/ {ano_atual}")
    
    # --- Linha de Assinatura ---
    y_pos -= 3.5 * cm
    c.setLineWidth(0.5)
    c.line(margin + 1*cm, y_pos, width - margin - 1*cm, y_pos)
    
    # --- Dados do Beneficiário ---
    y_pos -= 0.6 * cm
    c.setFont("Helvetica-Bold", 11)
    nome = getattr(pessoa, 'nome_completo', 'NOME NÃO INFORMADO').upper()
    c.drawCentredString(width / 2, y_pos, nome)
    
    y_pos -= 0.5 * cm
    c.setFont("Helvetica", 10)
    cpf = getattr(pessoa, 'cpf', '000.000.000-00')
    c.drawCentredString(width / 2, y_pos, f"CPF: {cpf}")
    
    endereco = ""
    if hasattr(pessoa, 'endereco'):
        endereco = pessoa.endereco
    elif hasattr(pessoa, 'rua'):
        endereco = f"{pessoa.rua}, {getattr(pessoa, 'numero', '')}"
        
    if endereco:
        y_pos -= 0.5 * cm
        c.drawCentredString(width / 2, y_pos, str(endereco))
    # --- Bairro e Cidade (Adicionado conforme solicitado) ---
    bairro = getattr(pessoa, 'bairro', '')
    cidade = getattr(pessoa, 'cidade', 'Pocinhos/PB') # Padrão Pocinhos se não informado
    
    if bairro or cidade:
        y_pos -= 0.5 * cm
        # Formata como "Bairro - Cidade" ou apenas um deles se o outro faltar
        info_local = f"{bairro} - {cidade}" if bairro and cidade else (bairro or cidade)
        c.drawCentredString(width / 2, y_pos, str(info_local))

def gerar_recibo_paginas_separadas(pessoa):
    """Gera um buffer contendo duas páginas, cada uma com um recibo"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2.5 * cm
    
    # Primeira Página
    desenhar_conteudo_recibo(c, pessoa, width, height, margin)
    c.showPage()
    
    # Segunda Página
    desenhar_conteudo_recibo(c, pessoa, width, height, margin)
    c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer

def gerar_memorando_pdf(pessoa):
    """Gera memorando individual com mesmo estilo do memorando em massa"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    
    # --- Cabeçalho Oficial ---
    y_header = height - 1.5 * cm
    caminho_brasao = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'brasao.jpg')
    if caminho_brasao:
        c.drawImage(caminho_brasao, (width/2) - 0.75*cm, y_header - 1.5*cm, width=1.5*cm, height=1.5*cm, mask='auto')
        y_header -= 2.5 * cm
    else:
        y_header -= 1.0 * cm
        
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y_header, "ESTADO DA PARAÍBA")
    y_header -= 0.4 * cm
    c.drawCentredString(width / 2, y_header, "PREFEITURA MUNICIPAL DE POCINHOS")
    y_header -= 0.4 * cm
    c.drawCentredString(width / 2, y_header, "SECRETARIA MUNICIPAL DE ASSISTÊNCIA SOCIAL")
    
    # --- Título do Memorando ---
    y_header -= 1.2 * cm
    beneficio = pessoa.beneficio
    num_memo = getattr(beneficio, 'numero_memorando', '4092/2025')
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y_header, f"M E M O R A N D O Nº. {num_memo}")
    
    # --- Quadro de Informações (DE, PARA, ASSUNTO) ---
    y_quadro_top = y_header - 0.8 * cm
    quadro_height = 3.2 * cm
    c.setLineWidth(1)
    c.setStrokeColor(colors.navy)
    c.rect(margin, y_quadro_top - quadro_height, width - 2 * margin, quadro_height)
    c.setStrokeColor(colors.black)
    
    y_row1 = y_quadro_top - 0.7 * cm
    y_row2 = y_quadro_top - 1.4 * cm
    y_row3 = y_quadro_top - 2.6 * cm
    
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.navy)
    c.drawString(margin + 0.4 * cm, y_row1, "DE:")
    c.setFillColor(colors.navy)
    c.drawString(margin + 0.4 * cm, y_row2, "PARA:")
    c.setFillColor(colors.black)
    c.drawString(margin + 0.4 * cm, y_row3, "ASSUNTO:")
    
    c.setFont("Helvetica", 10)
    c.drawString(margin + 3 * cm, y_row1, "SECRETARIA DE ASSISTÊNCIA SOCIAL")
    
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.navy)
    c.drawString(margin + 3 * cm, y_row2, "SECRETARIA DE FINANÇAS")
    c.setFont("Helvetica", 9)
    c.drawString(margin + 3 * cm, y_row2 - 0.5 * cm, "Att: Sr. Carlos Roberto Alves Filho – Secretário de Finanças")
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 3 * cm, y_row3, "Envio de pagamento.")
    
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - margin - 0.4 * cm, y_row1, f"DATA: {data_hoje}")
    
    # --- Texto Introdutório ---
    y_texto_area_top = y_quadro_top - quadro_height
    
    styles = getSampleStyleSheet()
    style_intro = ParagraphStyle('Intro', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=14, alignment=TA_JUSTIFY)
    texto_intro = "Por meio do presente, solicito que sejam tomadas as medidas necessárias no sentido de que sejam empenhadas e pagas as despesas que seguem abaixo:"
    p_intro = Paragraph(texto_intro, style_intro)
    w_p, h_p = p_intro.wrap(width - 2 * margin, height)
    
    espacamento_fixo = 1.0 * cm
    y_texto_pos = y_texto_area_top - espacamento_fixo - h_p
    p_intro.drawOn(c, margin, y_texto_pos)
    
    # --- Tabela Individual ---
    y_tabela_top = y_texto_pos - espacamento_fixo
    
    valor = float(pessoa.valor_beneficio)
    valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    conta = getattr(beneficio, 'conta_pagadora', '19.849-8')
    
    data = [
        ["N.º", "Beneficiário", "Tipo de Benefício", "Valor", "Conta Pagadora"],
        ["1", pessoa.nome_completo, beneficio.nome, valor_fmt, conta]
    ]
    
    table = Table(data, colWidths=[1*cm, 6*cm, 4.5*cm, 2.5*cm, 3*cm])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    w_t, h_t = table.wrap(width - 2 * margin, height)
    y_tabela_pos = y_tabela_top - h_t
    table.drawOn(c, margin, y_tabela_pos)
    
    # --- Texto de Fechamento ---
    y_fim = y_tabela_pos - 2.0 * cm
    texto_fim = "Despeço-me cordialmente aproveitando a oportunidade para reiterar os nossos sentimentos de elevada estima e consideração e me deixando a disposição para o que precisar."
    p_fim = Paragraph(texto_fim, style_intro)
    w_f, h_f = p_fim.wrap(width - 2 * margin, height)
    p_fim.drawOn(c, margin, y_fim)
    
    y_fim -= 1 * cm
    c.setFont("Helvetica", 11)
    c.drawString(margin, y_fim, "Atenciosamente,")
    
    # --- Assinatura ---
    y_assinatura = y_fim - 2.5 * cm
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, y_assinatura, "Zélia Maria Matias e Silva")
    y_assinatura -= 0.5 * cm
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, y_assinatura, "Secretária Adjunta de Assistência Social")
    
    # --- Rodapé ---
    c.setLineWidth(0.5)
    c.line(margin, 5.5 * cm, width - margin, 5.5 * cm)
    
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, 5.1 * cm, "Rua Pç. Pres. Getúlio Vargas, 57, Centro")
    c.drawCentredString(width / 2, 4.7 * cm, "CEP: 58150-000   –   Pocinhos – PB")
    c.drawCentredString(width / 2, 4.3 * cm, "e-mail: assistenciasocialpocinhos@gmail.com")
    
    c.save()
    buffer.seek(0)
    return buffer

def gerar_memorando_massa_pdf(beneficio, pessoas):
    """Gera memorando em massa com paginação segura."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    
    # Configurações
    altura_linha = 0.7 * cm
    margem_inferior_tabela = 2 * cm
    espaco_fechamento = 5.5 * cm  # Espaço necessário para fechamento + assinatura
    
    # Definição das larguras e posições X das colunas
    col_widths = [1.0*cm, 6.0*cm, 4.5*cm, 2.5*cm, 3.0*cm]
    total_table_width = sum(col_widths)
    table_margin = (width - total_table_width) / 2
    
    col_x_starts = [table_margin]
    for w in col_widths[:-1]:
        col_x_starts.append(col_x_starts[-1] + w)
    
    styles = getSampleStyleSheet()
    style_intro = ParagraphStyle('Intro', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=14, alignment=TA_JUSTIFY)
    
    def desenhar_cabecalho_pagina():
        """Desenha cabeçalho completo (brasão, títulos, quadro DE/PARA)"""
        y = height - 1.5 * cm
        
        # Brasão
        caminho_brasao = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'brasao.jpg')
        if os.path.exists(caminho_brasao):
            c.drawImage(caminho_brasao, (width/2) - 0.75*cm, y - 1.5*cm, width=1.5*cm, height=1.5*cm, mask='auto')
        y -= 2.5 * cm
        
        # Títulos
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.black)
        c.drawCentredString(width / 2, y, "ESTADO DA PARAÍBA")
        y -= 0.4 * cm
        c.drawCentredString(width / 2, y, "PREFEITURA MUNICIPAL DE POCINHOS")
        y -= 0.4 * cm
        c.drawCentredString(width / 2, y, "SECRETARIA MUNICIPAL DE ASSISTÊNCIA SOCIAL")
        
        # Título do Memorando
        y -= 1.2 * cm
        num_memo = getattr(beneficio, 'numero_memorando', '4092/2025')
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, y, f"M E M O R A N D O Nº. {num_memo}")
        
        # Quadro DE/PARA/ASSUNTO
        y_quadro_top = y - 0.8 * cm
        quadro_height = 3.2 * cm
        c.setLineWidth(1)
        c.setStrokeColor(colors.navy)
        c.rect(margin, y_quadro_top - quadro_height, width - 2 * margin, quadro_height)
        c.setStrokeColor(colors.black)
        
        y_row1 = y_quadro_top - 0.7 * cm
        y_row2 = y_quadro_top - 1.4 * cm
        y_row3 = y_quadro_top - 2.6 * cm
        
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.navy)
        c.drawString(margin + 0.4 * cm, y_row1, "DE:")
        c.drawString(margin + 0.4 * cm, y_row2, "PARA:")
        c.setFillColor(colors.black)
        c.drawString(margin + 0.4 * cm, y_row3, "ASSUNTO:")
        
        c.setFont("Helvetica", 10)
        c.drawString(margin + 3 * cm, y_row1, "SECRETARIA DE ASSISTÊNCIA SOCIAL")
        
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.navy)
        c.drawString(margin + 3 * cm, y_row2, "SECRETARIA DE FINANÇAS")
        c.setFont("Helvetica", 9)
        c.drawString(margin + 3 * cm, y_row2 - 0.5 * cm, "Att: Sr. Carlos Roberto Alves Filho – Secretário de Finanças")
        
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin + 3 * cm, y_row3, "Envio de pagamento.")
        
        data_hoje = datetime.now().strftime("%d/%m/%Y")
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(width - margin - 0.4 * cm, y_row1, f"DATA: {data_hoje}")
        
        # Texto introdutório
        y_texto = y_quadro_top - quadro_height - 1.0 * cm
        texto_intro = "Por meio do presente, solicito que sejam tomadas as medidas necessárias no sentido de que sejam empenhadas e pagas as despesas que seguem abaixo:"
        p_intro = Paragraph(texto_intro, style_intro)
        w_p, h_p = p_intro.wrap(width - 2 * margin, height)
        y_texto -= h_p
        p_intro.drawOn(c, margin, y_texto)
        
        return y_texto - 1.0 * cm
    
    def desenhar_cabecalho_tabela(y_pos):
        """Desenha apenas o cabeçalho da tabela"""
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        header_y_bottom = y_pos - 0.7*cm
        
        c.rect(table_margin, header_y_bottom, total_table_width, 0.7*cm)
        
        current_x = table_margin
        for w in col_widths:
            c.line(current_x, y_pos, current_x, header_y_bottom)
            current_x += w
        c.line(current_x, y_pos, current_x, header_y_bottom)
        
        y_text = y_pos - 0.5*cm
        c.drawCentredString(col_x_starts[0] + col_widths[0]/2, y_text, "N.º")
        c.drawCentredString(col_x_starts[1] + col_widths[1]/2, y_text, "Beneficiário")
        c.drawCentredString(col_x_starts[2] + col_widths[2]/2, y_text, "Tipo de Benefício")
        c.drawCentredString(col_x_starts[3] + col_widths[3]/2, y_text, "Valor")
        c.drawCentredString(col_x_starts[4] + col_widths[4]/2, y_text, "Conta Pagadora")
        
        return header_y_bottom
    
    def desenhar_fechamento_assinatura(y_pos):
        """Desenha bloco de fechamento e assinatura"""
        c.setFillColor(colors.black)
        
        # Texto de fechamento
        texto_fim = "Despeço-me cordialmente aproveitando a oportunidade para reiterar os nossos sentimentos de elevada estima e consideração e me deixando a disposição para o que precisar."
        p_fim = Paragraph(texto_fim, style_intro)
        w_f, h_f = p_fim.wrap(width - 2 * margin, height)
        y_pos -= h_f
        p_fim.drawOn(c, margin, y_pos)
        
        # Atenciosamente
        y_pos -= 1.2 * cm
        c.setFont("Helvetica", 11)
        c.drawString(margin, y_pos, "Atenciosamente,")
        
        # Assinatura
        y_pos -= 2 * cm
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2, y_pos, "Zélia Maria Matias e Silva")
        y_pos -= 0.5 * cm
        c.setFont("Helvetica", 12)
        c.drawCentredString(width / 2, y_pos, "Secretária Adjunta de Assistência Social")
        
        # Rodapé
        y_rodape = 2 * cm
        c.setLineWidth(0.5)
        c.line(margin, y_rodape, width - margin, y_rodape)
        
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        c.drawCentredString(width / 2, y_rodape - 0.4 * cm, "Rua Pç. Pres. Getúlio Vargas, 57, Centro")
        c.drawCentredString(width / 2, y_rodape - 0.8 * cm, "CEP: 58150-000   –   Pocinhos – PB")
        c.drawCentredString(width / 2, y_rodape - 1.2 * cm, "e-mail: assistenciasocialpocinhos@gmail.com")
    
    # --- INÍCIO DA GERAÇÃO ---
    
    # Primeira página com cabeçalho completo
    y_atual = desenhar_cabecalho_pagina()
    y_atual = desenhar_cabecalho_tabela(y_atual)
    
    c.setFont("Helvetica", 9)
    
    for idx, pessoa in enumerate(pessoas, 1):
        # Verifica se precisa de nova página
        if y_atual - altura_linha < margem_inferior_tabela:
            c.showPage()
            y_atual = height - 1.5 * cm
            y_atual = desenhar_cabecalho_tabela(y_atual)
            c.setFont("Helvetica", 9)
        
        # Desenha linha da tabela
        y_bottom = y_atual - altura_linha
        c.setFillColor(colors.black)
        c.rect(table_margin, y_bottom, total_table_width, altura_linha)
        
        current_x = table_margin
        for w in col_widths:
            c.line(current_x, y_atual, current_x, y_bottom)
            current_x += w
        c.line(current_x, y_atual, current_x, y_bottom)
        
        # Dados
        valor = float(pessoa.valor_beneficio)
        valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        conta = getattr(beneficio, 'conta_pagadora', '19.849-8')
        
        y_text = y_atual - 0.5 * cm
        c.drawCentredString(col_x_starts[0] + col_widths[0]/2, y_text, str(idx))
        c.drawCentredString(col_x_starts[1] + col_widths[1]/2, y_text, pessoa.nome_completo[:38])
        c.drawCentredString(col_x_starts[2] + col_widths[2]/2, y_text, beneficio.nome[:38])
        c.drawCentredString(col_x_starts[3] + col_widths[3]/2, y_text, valor_fmt)
        c.drawCentredString(col_x_starts[4] + col_widths[4]/2, y_text, str(conta)[:12])
        
        y_atual = y_bottom
    
    # Verifica se há espaço para fechamento + assinatura
    if y_atual - espaco_fechamento < 2 * cm:
        c.showPage()
        y_atual = height - 3 * cm
    
    # Desenha fechamento e assinatura
    desenhar_fechamento_assinatura(y_atual - 1.5 * cm)
    
    c.save()
    buffer.seek(0)
    return buffer
    
def gerar_recibos_massa_pdf(pessoas):
    """Gera recibos em massa (2 vias para cada pessoa)"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2.5 * cm
    
    for pessoa in pessoas:
        # Primeira via
        desenhar_conteudo_recibo(c, pessoa, width, height, margin)
        c.showPage()
        
        # Segunda via
        desenhar_conteudo_recibo(c, pessoa, width, height, margin)
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer
    
def gerar_documentos_massa_pdf(pessoas):
    """Gera PDF consolidado com documentos (2 vias, máx 4 páginas cada) usando disco"""
    import tempfile
    from PyPDF2 import PdfWriter, PdfReader
    
    # Usa arquivo temporário em disco
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_path = tmp_file.name
    
    writer = PdfWriter()
    arquivos_abertos = []
    
    try:
        for pessoa in pessoas:
            arquivo_path = pessoa.documento.arquivo.path
            
            try:
                pdf_file = open(arquivo_path, 'rb')
                arquivos_abertos.append(pdf_file)
                
                reader = PdfReader(pdf_file)
                total_paginas = min(len(reader.pages), 4)
                
                # 1ª via
                for i in range(total_paginas):
                    writer.add_page(reader.pages[i])
                
                # 2ª via
                for i in range(total_paginas):
                    writer.add_page(reader.pages[i])
                    
            except Exception:
                raise Exception(f"Erro ao processar documento de {pessoa.nome_completo}. Arquivo pode estar corrompido.")
        
        # Escreve no arquivo temporário
        with open(tmp_path, 'wb') as output_file:
            writer.write(output_file)
        
        # Lê o arquivo final para retornar
        with open(tmp_path, 'rb') as final_file:
            buffer = BytesIO(final_file.read())
        
        return buffer
        
    finally:
        # Fecha todos os arquivos abertos
        for f in arquivos_abertos:
            try:
                f.close()
            except:
                pass
        
        # Remove arquivo temporário
        if os.path.exists(tmp_path):
            os.remove(tmp_path)