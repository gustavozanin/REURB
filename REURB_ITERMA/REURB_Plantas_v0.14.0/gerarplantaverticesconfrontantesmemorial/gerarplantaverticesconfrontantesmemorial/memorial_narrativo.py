# -*- coding: utf-8 -*-
"""Memorial descritivo narrativo: texto corrido + preenchimento do
TextElement `memorial_texto` do layout `Layout_Memorial_Descritivo_A4`.

A lógica pura (`gerar_texto_memorial`, `partir_texto_memorial`) não
depende de ArcPy e é testável isoladamente (ver
`_TI_apenas/tests_memorial/test_memorial_narrativo.py`). `preencher_layout_memorial`
é um wrapper ArcPy fino, que levanta `RuntimeError` com uma mensagem clara
enquanto os layouts (T0.2, ver `layout/LEIA-ME_LAYOUTS.txt`) não existirem.

Sobre os nomes de campo aceitos em `segmentos` (dict ou objeto), ver a
docstring de `quadro_coordenadas.py` — a mesma flexibilidade (`de`/`vertice`,
`confrontante`/`confrontantes`, `distancia_m`/`distancia`, `E`/`eLong`,
`N`/`nLat`) é usada aqui.
"""

import os

try:
    import arcpy
except ImportError:
    arcpy = None

try:
    from caminhos_gerais import nome_layout_memorial as NOME_LAYOUT_MEMORIAL
except ImportError:
    NOME_LAYOUT_MEMORIAL = 'Layout_Memorial_Descritivo_A4'

from exportar_pdf_unificado import exportar_pdf_layout

# Limite conservador de caracteres por folha A4 no TextElement do layout
# Layout_Memorial_Descritivo_A4 (ver layout/LEIA-ME_LAYOUTS.txt). Ajustar
# aqui se, ao criar o layout real no Pro, o TextElement comportar mais
# ou menos texto por folha sem estourar a área definida.
MAX_CARACTERES_TEXTELEMENT_MEMORIAL = 4500

NOME_TEXT_ELEMENT_MEMORIAL = 'memorial_texto'

MENSAGEM_ELEMENTO_AUSENTE = (
    'Layout "{layout}" (TextElement "{elemento}") ainda não existe no '
    'project_layout.aprx desta ferramenta. Crie os layouts no ArcGIS Pro '
    'conforme layout/LEIA-ME_LAYOUTS.txt (T0.2) antes de gerar o memorial em PDF.'
)


def _valor(segmento, chaves, default=''):
    """Busca o primeiro valor presente em `segmento` entre `chaves`.

    Ver docstring equivalente em `quadro_coordenadas._valor` — mesma
    convenção usada nos dois módulos para aceitar tanto a feição ArcPy
    quanto o dict "de design" do memorial.
    """
    for chave in chaves:
        if isinstance(segmento, dict):
            if chave in segmento and segmento[chave] is not None:
                return segmento[chave]
        elif hasattr(segmento, chave):
            valor = getattr(segmento, chave)
            if valor is not None:
                return valor
    return default


def _formatar_numero_br(valor, casas=2, milhar=True):
    """Formata número em pt-BR: vírgula decimal e, se `milhar`, ponto de
    milhar (estilo do texto narrativo — diferente do CSV, que não usa
    separador de milhar; ver `quadro_coordenadas._formatar_numero_br`).
    """
    if valor is None or valor == '':
        return ''
    numero = float(valor)
    if milhar:
        texto = f'{numero:,.{casas}f}'
        texto = texto.replace(',', '_').replace('.', ',').replace('_', '.')
    else:
        texto = f'{numero:.{casas}f}'.replace('.', ',')
    return texto


def _montar_cabecalho(meta):
    """Monta o cabeçalho opcional do memorial a partir de `meta`
    (bairro, município, área, perímetro, processo, fuso). Campos
    ausentes em `meta` simplesmente não aparecem — cabeçalho é opcional.
    """
    meta = meta or {}
    linhas = []

    numero_reurb = (
        meta.get('numero_reurb') or meta.get('numeroProcessoColetivo') or meta.get('processo')
    )
    if numero_reurb:
        linhas.append(f'Processo REURB: {numero_reurb}')

    if meta.get('bairro'):
        linhas.append(f'Bairro: {meta["bairro"]}')

    if meta.get('municipio'):
        uf = meta.get('uf', '')
        municipio_txt = f'{meta["municipio"]}/{uf}' if uf else meta['municipio']
        linhas.append(f'Município: {municipio_txt}')

    if meta.get('area_m2') is not None:
        linhas.append(f'Área: {_formatar_numero_br(meta["area_m2"])} m²')

    if meta.get('perimetro_m') is not None:
        linhas.append(f'Perímetro: {_formatar_numero_br(meta["perimetro_m"])} m')

    if meta.get('fuso'):
        linhas.append(f'Fuso UTM: {meta["fuso"]}')

    return '\n'.join(linhas)


def _paragrafo_normativo(meta):
    """Parágrafo normativo padrão SIRGAS 2000 / UTM / fuso do processo."""
    meta = meta or {}
    fuso = meta.get('fuso') or 'não informado'
    return (
        'Todas as coordenadas, azimutes e distâncias descritos neste memorial '
        'estão referenciados ao Sistema Geodésico Brasileiro, Datum SIRGAS 2000, '
        f'projeção UTM, fuso {fuso}.'
    )


def gerar_texto_memorial(segmentos, meta=None):
    """
    Monta o texto corrido do memorial descritivo: cabeçalho opcional,
    "DESCRIÇÃO DO PERÍMETRO", narrativa encadeada dos segmentos (do
    vértice inicial até fechar de volta nele) e parágrafo normativo.

    Args:
        segmentos: lista ordenada de segmentos do perímetro (mesmo
            formato de `quadro_coordenadas.segmentos_para_linhas_csv`).
            Cada segmento deve trazer ao menos `de`, `azimute` e
            distância; `confrontante` e `para` são opcionais — se
            `para` não vier, é inferido do `de` do próximo segmento (e,
            no último segmento, do `de` do primeiro — fechamento do anel).
            As coordenadas E/N de cada vértice de destino saem no texto
            (`este_para`/`norte_para` ou o E/N do próximo segmento).
        meta: dict opcional com bairro, municipio, uf, area_m2,
            perimetro_m, numero_reurb, fuso, densidade, rt_* etc.

    Returns:
        str: texto completo do memorial, pronto para
        `partir_texto_memorial`/`preencher_layout_memorial`.

    Raises:
        ValueError: lista de segmentos vazia.
    """
    if not segmentos:
        raise ValueError('Lista de segmentos vazia; não é possível gerar o memorial.')

    meta = meta or {}
    blocos = []

    cabecalho = _montar_cabecalho(meta)
    if cabecalho:
        blocos.append(cabecalho)

    blocos.append('DESCRIÇÃO DO PERÍMETRO')

    primeiro = segmentos[0]
    primeiro_de = _valor(primeiro, ('de', 'vertice'), default='P-01')
    primeiro_e = _valor(primeiro, ('E', 'eLong'))
    primeiro_n = _valor(primeiro, ('N', 'nLat'))

    frase_inicial = (
        f'Inicia-se a descrição no vértice {primeiro_de}, '
        f'na coordenada E= {_formatar_numero_br(primeiro_e, casas=4)} m e '
        f'N= {_formatar_numero_br(primeiro_n, casas=4)} m'
    )
    bairro = meta.get('bairro')
    municipio = meta.get('municipio')
    if bairro or municipio:
        uf = meta.get('uf', '')
        local = ', '.join(parte for parte in (bairro, municipio) if parte)
        frase_inicial += f', situado no {local}{"/" + uf if uf else ""}'
    frase_inicial += '.'
    blocos.append(frase_inicial)

    total = len(segmentos)
    frases_segmento = []
    for indice, segmento in enumerate(segmentos):
        azimute = _valor(segmento, ('azimute',))
        distancia = _valor(segmento, ('distancia_m', 'distancia'))
        from constantes import CONFRONTANTE_PADRAO

        confrontante = _valor(
            segmento, ('confrontante', 'confrontantes'), default=CONFRONTANTE_PADRAO
        ) or CONFRONTANTE_PADRAO

        para_explicito = _valor(segmento, ('para', 'vertice_para'), default=None)
        if para_explicito:
            para = para_explicito
        elif indice + 1 < total:
            para = _valor(segmentos[indice + 1], ('de', 'vertice'), default='')
        else:
            para = primeiro_de

        para_e = _valor(segmento, ('este_para',))
        para_n = _valor(segmento, ('norte_para',))
        if para_e == '' or para_n == '':
            if indice + 1 < total:
                para_e = _valor(segmentos[indice + 1], ('E', 'eLong'))
                para_n = _valor(segmentos[indice + 1], ('N', 'nLat'))
            else:
                para_e = primeiro_e
                para_n = primeiro_n
        trecho_coord = (
            f', de coordenadas E={_formatar_numero_br(para_e, casas=4)} e '
            f'N={_formatar_numero_br(para_n, casas=4)}'
        )

        eh_ultimo = indice == total - 1
        origem = _valor(segmento, ('de', 'vertice'), default=primeiro_de)
        distancia_fmt = _formatar_numero_br(distancia, casas=2, milhar=False)
        prefixo = (
            f'Do vértice {origem}, confrontando com {confrontante}, segue '
            f'com azimute de {azimute} e distância de {distancia_fmt} m'
        )

        if eh_ultimo:
            frase = (
                f'{prefixo}, retornando ao vértice inicial {para}'
                f'{trecho_coord}, fechando assim o perímetro descrito.'
            )
        else:
            frase = (
                f'{prefixo} até o vértice {para}{trecho_coord}.'
            )
        frases_segmento.append(frase)

    blocos.append(' '.join(frases_segmento))
    blocos.append(_paragrafo_normativo(meta))

    return '\n\n'.join(blocos)


def _partir_por_frase(paragrafo, limite):
    """Fallback de `partir_texto_memorial` para parágrafo isolado maior
    que `limite`: corta em pontuação de frase (". ") em vez de parágrafo.
    """
    frases = paragrafo.split('. ')
    partes = []
    parte_atual = ''
    for indice, frase in enumerate(frases):
        sufixo = '. ' if indice < len(frases) - 1 else ''
        candidato = parte_atual + frase + sufixo
        if not parte_atual or len(candidato) <= limite:
            parte_atual = candidato
        else:
            partes.append(parte_atual)
            parte_atual = frase + sufixo
    if parte_atual:
        partes.append(parte_atual)
    return partes


def partir_texto_memorial(texto, limite=MAX_CARACTERES_TEXTELEMENT_MEMORIAL):
    """
    Divide o texto do memorial em partes de até `limite` caracteres,
    cortando preferencialmente em quebras de parágrafo (linha em branco)
    e, só se necessário, em pontuação de frase — para não estourar o
    TextElement de uma folha A4 sem quebrar o texto no meio de uma frase.

    Args:
        texto: texto completo (`gerar_texto_memorial`).
        limite: máximo de caracteres por parte/folha.

    Returns:
        list[str]: uma ou mais partes, cada uma <= `limite` caracteres
        (exceto se um único parágrafo/frase já ultrapassar o limite
        sozinho — nesse caso ele é mantido inteiro, sem inventar cortes
        no meio de uma frase).
    """
    if not texto:
        return ['']
    if len(texto) <= limite:
        return [texto]

    paragrafos = texto.split('\n\n')
    partes = []
    parte_atual = ''
    for paragrafo in paragrafos:
        candidato = f'{parte_atual}\n\n{paragrafo}' if parte_atual else paragrafo
        if len(candidato) <= limite:
            parte_atual = candidato
            continue

        if parte_atual:
            partes.append(parte_atual)
            parte_atual = ''

        if len(paragrafo) <= limite:
            parte_atual = paragrafo
        else:
            partes.extend(_partir_por_frase(paragrafo, limite))

    if parte_atual:
        partes.append(parte_atual)

    return partes


def preencher_layout_memorial(
    layout,
    texto,
    pasta_saida_pdfs,
    prefixo='memorial',
    nome_text_element=NOME_TEXT_ELEMENT_MEMORIAL,
    limite_caracteres=MAX_CARACTERES_TEXTELEMENT_MEMORIAL,
):
    """
    Preenche o TextElement `memorial_texto` do layout
    `Layout_Memorial_Descritivo_A4`, particionando o texto em folhas se
    necessário, e exporta um PDF por folha.

    Args:
        layout: objeto `arcpy._mp.Layout` já carregado (ver
            `gerar_planta_perimetro._obter_layout`).
        texto: texto completo do memorial (`gerar_texto_memorial`).
        pasta_saida_pdfs: pasta (normalmente `arcpy.env.scratchFolder`)
            onde os PDFs parciais serão gravados.
        prefixo: prefixo do nome de arquivo dos PDFs parciais.
        nome_text_element: nome do TextElement no layout (ver
            layout/LEIA-ME_LAYOUTS.txt).
        limite_caracteres: repassado a `partir_texto_memorial`.

    Returns:
        list[os.PathLike]: caminhos dos PDFs parciais, na ordem das folhas.

    Raises:
        RuntimeError: se ArcPy não estiver disponível, ou se o TextElement
            não existir no layout (layouts T0.2 ainda não criados).
    """
    if arcpy is None:
        raise RuntimeError('arcpy não disponível neste ambiente.')

    elementos = layout.listElements(element_type='TEXT_ELEMENT', wildcard=nome_text_element)
    if not elementos:
        raise RuntimeError(
            MENSAGEM_ELEMENTO_AUSENTE.format(
                layout=NOME_LAYOUT_MEMORIAL, elemento=nome_text_element
            )
        )

    elemento_texto = elementos[0]
    partes = partir_texto_memorial(texto, limite=limite_caracteres)
    total = len(partes)

    pdfs = []
    for indice, parte in enumerate(partes, start=1):
        elemento_texto.text = parte
        nome_pdf = f'{prefixo}_folha{indice:02d}.pdf' if total > 1 else f'{prefixo}.pdf'
        caminho_pdf = os.path.join(pasta_saida_pdfs, nome_pdf)
        exportar_pdf_layout(layout, caminho_pdf)
        pdfs.append(caminho_pdf)

    return pdfs
