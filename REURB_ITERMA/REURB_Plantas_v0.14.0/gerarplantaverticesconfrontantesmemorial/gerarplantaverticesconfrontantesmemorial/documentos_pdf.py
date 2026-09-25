# -*- coding: utf-8 -*-
"""Memorial, quadro e termo paginados, independentes de layouts ArcGIS.

Visual alinhado ao memorial institucional de
`C:\\REURB\\ferramentas\\gerarplantanucleo\\gerar_memorial_descritivo.py`
(brasão, logo do governo, quadro de identificação, nota técnica,
descrição narrada, parágrafo normativo e assinatura do RT).

Memorial e termo saem em A4 retrato. O Quadro de Confrontações sai em A3
paisagem, no mesmo tamanho da planta, com a lista distribuída em blocos
lado a lado (ver `gerar_quadro`).
"""

import html
import math
import sys
from pathlib import Path

# O Pro ignora pacotes da pasta do usuário. ReportLab fica em libs/,
# junto com a ferramenta — o analista não instala nada no Python do Pro.
_LIBS = Path(__file__).resolve().parent / 'libs'
if _LIBS.is_dir() and str(_LIBS) not in sys.path:
    sys.path.append(str(_LIBS))

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A3, A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import (
        HRFlowable,
        Image,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:
    raise ImportError(
        'Pacote reportlab não encontrado. Use o pacote REURB Plantas '
        'completo (a pasta libs desta ferramenta precisa vir junto; '
        'não copie só o .pyt).'
    ) from exc

from constantes import (
    CONFRONTANTE_PADRAO,
    TEXTO_ALCANCE_SELO,
    TEXTO_LIMITE_SELO,
    TITULO_QUADRO,
)

_ASSETS = Path(__file__).resolve().parent / 'layout' / 'assets'
BRASAO_PATH = _ASSETS / 'brasao_maranhao.png'
LOGO_GOVERNO_PATH = _ASSETS / 'logo_governo_maranhao.png'


def _br(value, decimals=4):
    if value is None or value == '':
        return ''
    return f"{float(value):,.{decimals}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


# Colunas do Quadro de Confrontações, iguais às da tabela da planta A3
# (ver os alias em `formatar_tabela_atributos.py`), para que o leitor
# encontre a mesma estrutura nas duas folhas.
COLUNAS_QUADRO = (
    'De', 'Para', 'Azimute', 'Distância (m)', 'Coord. E (x)',
    'Coord. N (y)', 'Confrontantes',
)

# Área útil das folhas A4 (memorial e termo) e da folha A3 do Quadro.
LARGURA_UTIL_A4 = 16.6 * cm
PAGINA_QUADRO = landscape(A3)
MARGEM_LATERAL_QUADRO = 1.5 * cm
LARGURA_UTIL_QUADRO = PAGINA_QUADRO[0] - 2 * MARGEM_LATERAL_QUADRO

# Blocos de linhas impressos lado a lado na folha do Quadro, como no anexo
# da ferramenta do núcleo (`gerarplantanucleo/gerar_planta.py`, que usa
# `columns=2` no Table Frame). Dois blocos cabem a lista inteira dos
# processos usuais em uma folha; acima de dois, a coluna de confrontantes
# fica estreita demais para os nomes de logradouro.
BLOCOS_QUADRO = 2
GAP_BLOCOS_QUADRO = 0.8 * cm
LARGURA_BLOCO_QUADRO = (
    LARGURA_UTIL_QUADRO - GAP_BLOCOS_QUADRO * (BLOCOS_QUADRO - 1)
) / BLOCOS_QUADRO

# Fração da largura do bloco por coluna, na ordem de `COLUNAS_QUADRO`.
# Proporções em vez de medidas fixas para a soma fechar exatamente com a
# largura do bloco, mesmo mudando margem ou número de blocos.
PROPORCOES_QUADRO = (0.060, 0.060, 0.123, 0.094, 0.115, 0.128, 0.420)
LARGURAS_BLOCO_QUADRO = [
    fracao * LARGURA_BLOCO_QUADRO for fracao in PROPORCOES_QUADRO
]

# Corpo das linhas do Quadro. O leading vai junto porque `FONTSIZE` no
# TableStyle não ajusta a entrelinha, e o default de 12 pt deixaria as
# linhas altas demais para a lista caber na folha.
FONTE_QUADRO = 7.0
LEADING_QUADRO = 8.0

# Quantas linhas cabem em cada bloco, medido na altura útil da folha
# depois do cabeçalho, do quadro de identificação, da nota e da
# assinatura. Estourar esse número não deforma a folha: o excedente vai
# para a página seguinte (ver `_blocos_lado_a_lado`).
LINHAS_POR_BLOCO_QUADRO = 40

def _vertice_destino(segmentos, indice):
    """Vértice final do segmento (coluna "Para" da tabela da planta).

    Usa o campo `vertice_para` quando vem preenchido; se faltar, assume a
    sequência da lista e fecha o polígono no último segmento.
    """
    destino = segmentos[indice].get('vertice_para')
    if destino:
        return str(destino)
    proximo = segmentos[(indice + 1) % len(segmentos)]
    return str(proximo.get('vertice') or '')


def _coordenada(valor, decimals=4):
    """Formata coordenada UTM sem separador de milhar.

    Mesmo formato da tabela da planta e do CSV do quadro (ver
    `quadro_coordenadas._formatar_numero_br`), para que o mesmo vértice
    apareça idêntico nos três lugares.
    """
    if valor is None or valor == '':
        return ''
    return f'{float(valor):.{decimals}f}'.replace('.', ',')


def _azimute(valor):
    return str(valor or '').replace('′', "'").replace('″', '"')


def _logo(path, width, height):
    if path.exists():
        return Image(str(path), width=width, height=height, kind='proportional')
    return ''


def _styles():
    base = getSampleStyleSheet()
    return {
        'orgao': ParagraphStyle(
            'Orgao', parent=base['Normal'], alignment=TA_LEFT,
            fontName='Helvetica-Bold', fontSize=11, leading=13,
        ),
        'orgao_sub': ParagraphStyle(
            'OrgaoSub', parent=base['Normal'], alignment=TA_LEFT,
            fontName='Helvetica', fontSize=8.1, leading=9.3,
            textColor=colors.HexColor('#333333'),
        ),
        'title': ParagraphStyle(
            'TitleMemorial', parent=base['Title'], alignment=TA_CENTER,
            fontName='Helvetica-Bold', fontSize=15, leading=18,
            spaceAfter=8, textColor=colors.HexColor('#111111'),
        ),
        'section': ParagraphStyle(
            'Section', parent=base['Heading2'], alignment=TA_CENTER,
            fontName='Helvetica-Bold', fontSize=10.8, leading=14,
            textColor=colors.HexColor('#111111'),
            spaceBefore=8, spaceAfter=8,
        ),
        'body': ParagraphStyle(
            'BodyJustify', parent=base['Normal'], alignment=TA_JUSTIFY,
            fontName='Helvetica', fontSize=9.15, leading=13.5,
            firstLineIndent=18,
        ),
        'cell': ParagraphStyle(
            'CellITERMA', parent=base['Normal'], fontSize=6.5, leading=7.5,
        ),
        'cell_quadro': ParagraphStyle(
            'CellQuadro', parent=base['Normal'],
            fontSize=FONTE_QUADRO, leading=LEADING_QUADRO,
        ),
        'mono': ParagraphStyle(
            'Mono', parent=base['Normal'], fontName='Courier',
            fontSize=7.2, leading=9,
        ),
        'normal': base['Normal'],
    }


def _cabecalho_institucional(styles, largura=LARGURA_UTIL_A4):
    header_text = [
        Paragraph('GOVERNO DO ESTADO DO MARANHÃO', styles['orgao']),
        Paragraph(
            'INSTITUTO DE COLONIZAÇÃO E TERRAS DO MARANHÃO - ITERMA',
            styles['orgao_sub'],
        ),
    ]
    header = Table(
        [[
            _logo(BRASAO_PATH, 1.38 * cm, 1.38 * cm),
            header_text,
            _logo(LOGO_GOVERNO_PATH, 3.55 * cm, 1.18 * cm),
            Paragraph(
                'ITERMA',
                ParagraphStyle(
                    'Iterma', parent=styles['orgao'], alignment=TA_CENTER,
                    fontSize=11.5, leading=12,
                ),
            ),
        ]],
        colWidths=[
            1.55 * cm,
            largura - (1.55 + 3.65 + 2.05) * cm,
            3.65 * cm,
            2.05 * cm,
        ],
    )
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.8, colors.black),
        ('LINEBEFORE', (3, 0), (3, 0), 0.6, colors.black),
    ]))
    return header


def _tabela_info(meta, styles, largura=LARGURA_UTIL_A4):
    bairro = html.escape(str(meta.get('bairro') or ''))
    municipio = html.escape(str(meta.get('municipio') or ''))
    uf = html.escape(str(meta.get('uf') or 'MA'))
    numero = html.escape(str(meta.get('numero_reurb') or ''))
    fuso = html.escape(str(meta.get('fuso') or ''))
    tabela = Table(
        [
            [
                Paragraph(f'<b>Bairro:</b> {bairro}', styles['normal']),
                Paragraph(f'<b>Município/UF:</b> {municipio} - {uf}', styles['normal']),
            ],
            [
                Paragraph(f"<b>Área:</b> {_br(meta.get('area_m2'), 2)} m²", styles['normal']),
                Paragraph(
                    f"<b>Perímetro:</b> {_br(meta.get('perimetro_m'), 2)} m",
                    styles['normal'],
                ),
            ],
            [
                Paragraph(f'<b>Processo REURB Coletivo:</b> {numero}', styles['normal']),
                Paragraph(f'<b>Fuso UTM:</b> {fuso}', styles['normal']),
            ],
        ],
        colWidths=[largura / 2.0, largura / 2.0],
    )
    tabela.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#333333')),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#999999')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F7F7F7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return tabela


def _nota_tecnica(styles, texto, largura=LARGURA_UTIL_A4):
    nota = Table(
        [[Paragraph(f'<b>Nota técnica:</b> {texto}', styles['normal'])]],
        colWidths=[largura],
    )
    nota.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#555555')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF7D6')),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return nota


def _meridiano_texto(meta):
    meridiano = meta.get('meridiano_central')
    try:
        return f'{abs(float(meridiano)):.0f}°'
    except Exception:
        fuso = str(meta.get('fuso') or '')
        digitos = ''.join(ch for ch in fuso if ch.isdigit())
        if digitos:
            try:
                return f'{abs(int(digitos) * 6 - 183)}°'
            except Exception:
                pass
        return '45°'


def _paragrafo_referencias(meta):
    fuso = html.escape(str(meta.get('fuso') or ''))
    meridiano = html.escape(_meridiano_texto(meta))
    return (
        'Todas as coordenadas aqui descritas estão plotadas na Carta Planimétrica '
        'Cadastral anexa, bem como georreferenciadas ao Sistema Geodésico Brasileiro '
        '(SGB), e encontram-se representadas na Projeção Universal Transversa de '
        f'Mercator (UTM), Fuso {fuso}, referenciadas ao Meridiano Central de '
        f'{meridiano}, tendo como datum horizontal o SIRGAS 2000 (elipsoide '
        'GRS-80/Sistema de Referência Geocêntrico para as Américas). A área foi '
        'obtida pelas coordenadas plano-retangulares referenciadas ao Sistema '
        'Geodésico Brasileiro (SGB). Todos os azimutes foram calculados no plano '
        'da projeção UTM. O perímetro e as distâncias foram calculados pelas '
        'coordenadas plano-retangulares. A execução do levantamento in situ '
        'atende aos parâmetros estabelecidos pelas Especificações e Normas para '
        'Levantamentos Geodésicos Associados ao Sistema Geodésico Brasileiro '
        '(IBGE, 2017), pelas normas da Associação Brasileira de Normas Técnicas '
        '(ABNT), especialmente a ABNT NBR 13.133 (2ª ed., 2021), Execução de '
        'Levantamento Topográfico, a ABNT NBR 17.047 (1ª ed., 2022), Levantamento '
        'Cadastral Territorial para Registro Público, e a Norma Técnica para '
        'Georreferenciamento de Imóveis Rurais (3ª ed., 2013), do Instituto '
        'Nacional de Colonização e Reforma Agrária (INCRA).'
    )


def _montar_descricao(segmentos):
    if not segmentos:
        return ''

    partes = []
    primeiro = segmentos[0]
    partes.append(
        'Inicia-se a descrição no vértice '
        f"<b>{html.escape(str(primeiro.get('vertice', '')))}</b>, na coordenada "
        f"E= {_br(primeiro.get('eLong'))} e N= {_br(primeiro.get('nLat'))}"
    )

    for indice, item in enumerate(segmentos):
        origem = html.escape(str(item.get('vertice') or ''))
        proximo = segmentos[(indice + 1) % len(segmentos)]
        destino = item.get('vertice_para') or proximo.get('vertice') or ''
        destino_item = next(
            (
                s for s in segmentos
                if str(s.get('vertice') or '') == str(destino)
            ),
            proximo,
        )
        confrontante = html.escape(
            str(item.get('confrontante') or CONFRONTANTE_PADRAO)
        )
        partes.append(
            f'do vértice <b>{origem}</b>, confrontando com {confrontante}, '
            f'segue com azimute de {_azimute(item.get("azimute"))} '
            f'e distância de {_br(item.get("distancia"))} m até o vértice '
            f"<b>{html.escape(str(destino))}</b>, de coordenada "
            f"E= {_br(destino_item.get('eLong'))} e "
            f"N= {_br(destino_item.get('nLat'))}"
        )

    partes.append('fechando assim o perímetro descrito.')
    return ', '.join(partes)


def _tabela_assinatura(meta):
    """Assinatura do RT. `splitByRow=0` já a mantém inteira numa página."""
    nome = str(meta.get('rt_nome') or '')
    formacao = str(meta.get('rt_formacao') or '')
    registro = str(meta.get('rt_crea') or '')
    linha_credencial = ' - '.join(valor for valor in [formacao, registro] if valor)
    assinatura = Table(
        [
            [''],
            ['____________________________________________'],
            [nome],
            [linha_credencial],
            ['Responsável Técnico'],
        ],
        colWidths=[10 * cm],
        splitByRow=0,
    )
    assinatura.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('TOPPADDING', (0, 0), (0, 0), 6),
    ]))
    return assinatura


def _bloco_assinatura(meta):
    return KeepTogether([_tabela_assinatura(meta)])


class _CanvasComRodape(Canvas):
    """Canvas que numera as páginas e imprime o protocolo no rodapé.

    O total de páginas só é conhecido no fim da montagem, então os estados
    das páginas ficam guardados e o rodapé é desenhado na hora de salvar.
    """

    def __init__(self, *args, identificacao_folha='', protocolo='', **kwargs):
        super().__init__(*args, **kwargs)
        self._identificacao_folha = identificacao_folha
        self._protocolo = protocolo
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._desenhar_rodape(total)
            super().showPage()
        super().save()

    def _desenhar_rodape(self, total):
        partes = [f'Página {self._pageNumber} de {total}']
        if self._identificacao_folha:
            partes.insert(0, self._identificacao_folha)
        centro = self._pagesize[0] / 2.0
        self.setFont('Helvetica', 7.5)
        self.setFillColor(colors.HexColor('#555555'))
        self.drawCentredString(centro, 0.8 * cm, ' — '.join(partes))
        if self._protocolo:
            self.setFont('Helvetica', 6.2)
            self.drawCentredString(
                centro, 0.5 * cm, f'Protocolo {self._protocolo}'
            )


def _canvas_com_rodape(identificacao_folha='', protocolo=''):
    def criar(*args, **kwargs):
        return _CanvasComRodape(
            *args,
            identificacao_folha=identificacao_folha,
            protocolo=protocolo,
            **kwargs,
        )

    return criar


def _document(path, title, pagesize=A4, margem_lateral=1.8 * cm):
    return SimpleDocTemplate(
        path,
        pagesize=pagesize,
        leftMargin=margem_lateral,
        rightMargin=margem_lateral,
        topMargin=1.25 * cm,
        bottomMargin=1.35 * cm,
        title=title,
    )


def gerar_memorial(segmentos, meta, path, selo=None):
    """
    Gera o memorial descritivo em A4.

    Args:
        segmentos: segmentos do perímetro.
        meta: metadados do processo (ver `_tabela_info`).
        path: caminho do PDF de saída.
        selo: dict do selo de autenticação (ver
            `autenticacao_documentos.montar_selo`); o protocolo sai no
            rodapé de todas as páginas.

    Returns:
        os.PathLike: o próprio `path`.
    """
    styles = _styles()
    story = [
        _cabecalho_institucional(styles),
        Spacer(1, 0.35 * cm),
        Paragraph('MEMORIAL DESCRITIVO', styles['title']),
        _tabela_info(meta, styles),
        Spacer(1, 0.35 * cm),
        _nota_tecnica(
            styles,
            'este memorial apresenta a descrição analítica completa do perímetro, '
            'com a sequência integral de vértices e coordenadas.',
        ),
        Spacer(1, 0.35 * cm),
        HRFlowable(width='100%', thickness=0.7, color=colors.HexColor('#333333')),
        Paragraph('DESCRIÇÃO DO PERÍMETRO', styles['section']),
        HRFlowable(width='100%', thickness=0.7, color=colors.HexColor('#333333')),
        Spacer(1, 0.25 * cm),
        Paragraph(_montar_descricao(segmentos), styles['body']),
        Spacer(1, 0.25 * cm),
        Paragraph(_paragrafo_referencias(meta), styles['body']),
        Spacer(1, 0.25 * cm),
        _bloco_assinatura(meta),
    ]
    _document(path, 'Memorial descritivo').build(
        story,
        canvasmaker=_canvas_com_rodape(
            protocolo=(selo or {}).get('protocolo', '')
        ),
    )
    return path


def _bloco_selo(styles, selo):
    """Quadro destacado com protocolo, data e código de conteúdo."""
    identificacao = [
        Paragraph(
            f"<b>Protocolo:</b> {html.escape(selo.get('protocolo', ''))}",
            styles['normal'],
        ),
        Spacer(1, 0.15 * cm),
        Paragraph(
            f"<b>Emitido em:</b> {html.escape(selo.get('emitido_em', ''))}",
            styles['normal'],
        ),
        Spacer(1, 0.15 * cm),
        Paragraph('<b>Código de conteúdo (SHA-256):</b>', styles['normal']),
        Paragraph(html.escape(selo.get('hash_conteudo', '')), styles['mono']),
    ]
    bloco = Table([[identificacao]], colWidths=[16.6 * cm])
    bloco.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#333333')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return bloco


def _tabela_hashes(styles, hashes):
    """Códigos SHA-256 dos arquivos entregues, conferíveis por terceiros."""
    linhas = [['Arquivo', 'SHA-256']]
    for rotulo, valor in hashes.items():
        linhas.append([
            Paragraph(html.escape(rotulo), styles['cell']),
            Paragraph(html.escape(valor or '(não gerado)'), styles['mono']),
        ])
    tabela = Table(linhas, colWidths=[3.6 * cm, 13.0 * cm])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9E2F3')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tabela


def gerar_termo_autenticacao(meta, selo, path):
    """
    Gera a folha de Termo de Autenticação, última página do pacote.

    Reúne o protocolo, o código de conteúdo e os códigos dos arquivos
    entregues, além do texto que delimita o alcance do selo (ver
    `constantes.TEXTO_ALCANCE_SELO` / `TEXTO_LIMITE_SELO`).

    Args:
        meta: metadados do processo (ver `_tabela_info`).
        selo: dict de `autenticacao_documentos.montar_selo`.
        path: caminho do PDF de saída.

    Returns:
        os.PathLike: o próprio `path`.
    """
    styles = _styles()
    story = [
        _cabecalho_institucional(styles),
        Spacer(1, 0.35 * cm),
        Paragraph('TERMO DE AUTENTICAÇÃO', styles['title']),
        _tabela_info(meta, styles),
        Spacer(1, 0.35 * cm),
        _bloco_selo(styles, selo),
        Spacer(1, 0.35 * cm),
        Paragraph('ALCANCE DESTE CÓDIGO', styles['section']),
        Paragraph(TEXTO_ALCANCE_SELO, styles['body']),
        Spacer(1, 0.2 * cm),
        Paragraph(TEXTO_LIMITE_SELO, styles['body']),
        Spacer(1, 0.35 * cm),
        Paragraph('COMO CONFERIR', styles['section']),
        Paragraph(
            'Os códigos dos '
            'arquivos listados abaixo podem ser conferidos com qualquer '
            'utilitário SHA-256 — no Windows, pelo comando '
            '<font face="Courier">certutil -hashfile ARQUIVO SHA256</font>. '
            'Já o código de conteúdo é reproduzido pela própria ferramenta '
            'do ITERMA, ao reprocessar a emissão a partir do mesmo '
            'levantamento.',
            styles['body'],
        ),
        Spacer(1, 0.3 * cm),
        _tabela_hashes(styles, selo.get('hashes_arquivos') or {}),
        Spacer(1, 0.5 * cm),
        _bloco_assinatura(meta),
    ]
    _document(path, 'Termo de autenticação').build(
        story,
        canvasmaker=_canvas_com_rodape(
            protocolo=selo.get('protocolo', '')
        ),
    )
    return path


def _bloco_quadro(segmentos, indices, styles):
    """Uma coluna de linhas do Quadro, com o cabeçalho das colunas no topo."""
    rows = [list(COLUNAS_QUADRO)]
    for indice in indices:
        item = segmentos[indice]
        confrontante = str(item.get('confrontante') or CONFRONTANTE_PADRAO)
        rows.append([
            str(item.get('vertice') or ''),
            _vertice_destino(segmentos, indice),
            _azimute(item.get('azimute')),
            _coordenada(item.get('distancia')),
            _coordenada(item.get('eLong')),
            _coordenada(item.get('nLat')),
            Paragraph(html.escape(confrontante), styles['cell_quadro']),
        ])
    bloco = Table(rows, colWidths=LARGURAS_BLOCO_QUADRO)
    bloco.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#C9C9C9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), FONTE_QUADRO),
        ('LEADING', (0, 0), (-1, -1), LEADING_QUADRO),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Vértices, azimute, distância e coordenadas centralizados como na
        # tabela da planta; só o nome do confrontante fica à esquerda.
        ('ALIGN', (0, 0), (-2, -1), 'CENTER'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    return bloco


def _repartir_em_blocos(indices):
    """
    Divide os índices de uma página entre os blocos, em partes iguais.

    Com 67 índices em dois blocos, saem 34 e 33 — a lista continua sendo
    lida de cima para baixo no bloco da esquerda e seguindo no da direita.

    Returns:
        list[list]: um grupo de índices por bloco.
    """
    tamanho = math.ceil(len(indices) / BLOCOS_QUADRO)
    return [
        indices[corte:corte + tamanho]
        for corte in range(0, len(indices), tamanho)
    ]


def _lado_a_lado(segmentos, indices, styles):
    """Monta os blocos de uma página alinhados lado a lado."""
    celulas = []
    larguras = []
    for grupo in _repartir_em_blocos(indices):
        if celulas:
            celulas.append('')
            larguras.append(GAP_BLOCOS_QUADRO)
        celulas.append(_bloco_quadro(segmentos, grupo, styles))
        larguras.append(LARGURA_BLOCO_QUADRO)
    container = Table([celulas], colWidths=larguras)
    container.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return container


def _fatias_por_pagina(segmentos, styles, altura_primeira, altura_seguintes):
    """
    Decide quais segmentos entram em cada página da folha do Quadro.

    Parte de `BLOCOS_QUADRO * LINHAS_POR_BLOCO_QUADRO` linhas por página e
    confere medindo a altura já montada: os blocos ficam numa única célula
    de tabela, que o ReportLab não quebra sozinho, e passar da altura do
    frame desenharia as últimas linhas sobre o rodapé. Não cabendo, tira
    linhas até caber e deixa o resto para a página seguinte — é o que
    acontece quando nomes de confrontante longos ocupam duas linhas.

    Args:
        segmentos: segmentos do perímetro.
        styles: estilos de `_styles`.
        altura_primeira: altura livre na primeira página, já descontados
            cabeçalho, quadro de identificação, nota e assinatura.
        altura_seguintes: altura livre nas páginas seguintes, que não
            repetem o cabeçalho.

    Returns:
        list[list]: índices dos segmentos de cada página, na ordem.
    """
    fatias = []
    inicio = 0
    while inicio < len(segmentos):
        disponivel = altura_seguintes if fatias else altura_primeira
        quantidade = min(
            len(segmentos) - inicio, BLOCOS_QUADRO * LINHAS_POR_BLOCO_QUADRO
        )
        while quantidade > BLOCOS_QUADRO:
            indices = list(range(inicio, inicio + quantidade))
            altura = _lado_a_lado(segmentos, indices, styles).wrap(
                LARGURA_UTIL_QUADRO, disponivel
            )[1]
            if altura <= disponivel:
                break
            quantidade = max(BLOCOS_QUADRO, int(quantidade * 0.9))
        fatias.append(list(range(inicio, inicio + quantidade)))
        inicio += quantidade
    return fatias


def _blocos_lado_a_lado(segmentos, styles, altura_primeira, altura_seguintes):
    """
    Distribui os segmentos em blocos lado a lado na folha do Quadro.

    Returns:
        list: flowables prontos para a story, já com as quebras de página.
    """
    flowables = []
    for indices in _fatias_por_pagina(
        segmentos, styles, altura_primeira, altura_seguintes
    ):
        if flowables:
            flowables.append(PageBreak())
        flowables.append(_lado_a_lado(segmentos, indices, styles))
    return flowables


def gerar_quadro(segmentos, meta, path, folha=None, selo=None):
    """
    Gera o Quadro de Confrontações em A3 paisagem, com rodapé numerado.

    Mesmo tamanho de folha da planta, com a lista de segmentos repartida
    em blocos lado a lado (ver `_blocos_lado_a_lado`), de modo que os
    processos usuais cabem em uma folha só.

    Args:
        segmentos: segmentos do perímetro (ver `formatar_dados_perimetro`).
        meta: metadados do processo (ver `_tabela_info`).
        path: caminho do PDF de saída.
        folha: rótulo da folha no pacote (ex.: '02/02') quando o quadro vai
            como folha adicional da planta; None quando avulso.
        selo: dict do selo de autenticação (ver
            `autenticacao_documentos.montar_selo`); o protocolo sai no
            rodapé de todas as páginas.

    Returns:
        os.PathLike: o próprio `path`.
    """
    styles = _styles()
    identificacao_folha = f'Folha {folha}' if folha else ''
    if folha:
        nota = (
            f'folha adicional da Planta (Folha {folha}), destacada em razão do '
            'espaço necessário à representação dos dados, nos termos do Art. '
            '176 da Lei nº 6.015/73. Traz o quadro analítico dos vértices do '
            'perímetro, com azimute, distância e confrontante de cada segmento.'
        )
    else:
        nota = (
            'quadro analítico dos vértices do perímetro, com azimute, '
            'distância e confrontante de cada segmento.'
        )

    doc = _document(
        path,
        'Quadro de confrontações',
        pagesize=PAGINA_QUADRO,
        margem_lateral=MARGEM_LATERAL_QUADRO,
    )
    topo = [
        _cabecalho_institucional(styles, LARGURA_UTIL_QUADRO),
        Spacer(1, 0.35 * cm),
        Paragraph(TITULO_QUADRO, styles['title']),
        _tabela_info(meta, styles, LARGURA_UTIL_QUADRO),
        Spacer(1, 0.35 * cm),
        _nota_tecnica(styles, nota, LARGURA_UTIL_QUADRO),
        Spacer(1, 0.35 * cm),
    ]
    rodape = [Spacer(1, 0.4 * cm), _tabela_assinatura(meta)]
    altura_topo = sum(
        item.wrap(LARGURA_UTIL_QUADRO, doc.height)[1] for item in topo
    )
    altura_rodape = sum(
        item.wrap(LARGURA_UTIL_QUADRO, doc.height)[1] for item in rodape
    )

    story = list(topo)
    story.extend(
        _blocos_lado_a_lado(
            segmentos,
            styles,
            altura_primeira=doc.height - altura_topo - altura_rodape,
            altura_seguintes=doc.height - altura_rodape,
        )
    )
    story.extend(rodape)
    doc.build(
        story,
        canvasmaker=_canvas_com_rodape(
            identificacao_folha, (selo or {}).get('protocolo', '')
        ),
    )
    return path
