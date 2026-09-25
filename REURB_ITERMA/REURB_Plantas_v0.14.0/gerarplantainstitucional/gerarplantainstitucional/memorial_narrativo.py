# -*- coding: utf-8 -*-
"""Memorial descritivo narrativo: texto corrido para PDF (ReportLab).

A lógica pura (`gerar_texto_memorial`) não depende de ArcPy. O PDF do
memorial no fluxo institucional é gerado via `documentos_pdf.gerar_memorial`.

Sobre os nomes de campo aceitos em `segmentos` (dict ou objeto), ver a
docstring de `quadro_coordenadas.py` — a mesma flexibilidade (`de`/`vertice`,
`confrontante`/`confrontantes`, `distancia_m`/`distancia`, `E`/`eLong`,
`N`/`nLat`) é usada aqui.
"""


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

    if meta.get('titulo') or meta.get('nome'):
        linhas.append(f'Imóvel: {meta.get("titulo") or meta.get("nome")}')

    if meta.get('quadra') is not None and str(meta.get('quadra')).strip() != '':
        linhas.append(f'Quadra: {meta["quadra"]}')

    if meta.get('lote') is not None and str(meta.get('lote')).strip() != '':
        linhas.append(f'Lote: {meta["lote"]}')

    if meta.get('status_rotulo'):
        linhas.append(f'Status: {meta["status_rotulo"]}')

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
        str: texto completo do memorial, pronto para o PDF ReportLab.

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
        # Confrontante no De, igual à linha De→Para da tabela.
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
