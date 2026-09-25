# -*- coding: utf-8 -*-
"""Quadro de coordenadas: CSV (`De;Confrontante;Azimute;Distancia (m);E;N`).

A lógica pura (`segmentos_para_linhas_csv`, `exportar_csv`) não depende de
ArcPy. O PDF do quadro no fluxo institucional é gerado via ReportLab
(`documentos_pdf.gerar_quadro`).

Os segmentos aceitos vêm de duas origens equivalentes já usadas nesta
ferramenta (ver `formatar_dados_perimetro.py` e o modelo `SegmentoMemorial`
do design), com nomes de chave ligeiramente diferentes:

    - feição ArcPy (`formatar_tabela_atributos.py`): de, para, azimute,
      distancia, E, N, confrontantes (plural)
    - dict "de design" (`.specs/.../design.md`): de, para, azimute,
      distancia_m, E, N, confrontante (singular)

Por isso `_valor` aceita qualquer uma das variantes de nome de campo.
"""

import csv

CABECALHO_CSV = ('De', 'Confrontante', 'Azimute', 'Distancia (m)', 'E', 'N')


def _valor(segmento, chaves, default=''):
    """Busca o primeiro valor presente em `segmento` entre `chaves`.

    Aceita `segmento` como dict (chaves por nome) ou objeto com atributos
    homônimos. Retorna `default` (string vazia por padrão — ver AC4 da
    spec: confrontante ausente vira string vazia explícita, nunca None).
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


def _formatar_numero_br(valor, casas=4):
    """Formata um número com vírgula decimal e sem separador de milhar.

    Referência do CSV oficial: `89,4004` e `515894,2441` — vírgula
    decimal, nenhum ponto de milhar.
    """
    if valor is None or valor == '':
        return ''
    numero = float(valor)
    texto = f'{numero:.{casas}f}'
    return texto.replace('.', ',')


def segmentos_para_linhas_csv(segmentos):
    """
    Monta as linhas de texto do CSV do quadro de coordenadas, já com o
    separador `;` e o cabeçalho oficial.

    Args:
        segmentos: lista de segmentos (dict ou objeto), cada um com
            de/para, confrontante(s), azimute, distância e E/N (ver
            docstring do módulo para os nomes de campo aceitos).

    Returns:
        list[str]: primeira linha é o cabeçalho
        `De;Confrontante;Azimute;Distancia (m);E;N`; as demais, uma por
        segmento, na mesma ordem recebida.
    """
    linhas = [';'.join(CABECALHO_CSV)]

    for segmento in segmentos:
        de = _valor(segmento, ('de', 'vertice'))
        confrontante = _valor(segmento, ('confrontante', 'confrontantes'))
        azimute = _valor(segmento, ('azimute',))
        distancia = _valor(segmento, ('distancia_m', 'distancia'))
        e_coord = _valor(segmento, ('E', 'eLong'))
        n_coord = _valor(segmento, ('N', 'nLat'))

        linha = ';'.join(
            (
                str(de),
                str(confrontante),
                str(azimute),
                _formatar_numero_br(distancia),
                _formatar_numero_br(e_coord),
                _formatar_numero_br(n_coord),
            )
        )
        linhas.append(linha)

    return linhas


def exportar_csv(segmentos, path):
    """
    Escreve o CSV do quadro de coordenadas em `path`.

    Usa `utf-8-sig` (BOM) para abrir corretamente no Excel em pt-BR, sem
    reinterpretar caracteres acentuados dos nomes de confrontante.

    Args:
        segmentos: ver `segmentos_para_linhas_csv`.
        path: caminho do arquivo `.csv` de saída (diretório deve existir).

    Returns:
        os.PathLike: o próprio `path`, para encadeamento.
    """
    linhas = segmentos_para_linhas_csv(segmentos)
    with open(path, 'w', newline='', encoding='utf-8-sig') as arquivo:
        escritor = csv.writer(arquivo, delimiter=';', lineterminator='\r\n')
        for linha in linhas:
            escritor.writerow(linha.split(';'))
    return path
