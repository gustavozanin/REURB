# -*- coding: utf-8 -*-
"""Quadro de coordenadas: CSV (`De;Confrontante;Azimute;Distancia (m);E;N`)
e preenchimento do Table Frame do layout `Layout_Quadro_Coordenadas_A4`.

A lógica pura (`segmentos_para_linhas_csv`, `exportar_csv`) não depende de
ArcPy e é testável isoladamente (ver
`_TI_apenas/tests_memorial/test_quadro_coordenadas.py`). `preencher_layout_quadro`
é um wrapper ArcPy fino, que levanta `RuntimeError` com uma mensagem clara
enquanto os layouts (T0.2, ver `layout/LEIA-ME_LAYOUTS.txt`) não existirem.

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
import os

try:
    import arcpy
except ImportError:
    arcpy = None

try:
    from caminhos_gerais import nome_layout_quadro as NOME_LAYOUT_QUADRO
except ImportError:
    NOME_LAYOUT_QUADRO = 'Layout_Quadro_Coordenadas_A4'

from exportar_pdf_unificado import exportar_pdf_layout

CABECALHO_CSV = ('De', 'Confrontante', 'Azimute', 'Distancia (m)', 'E', 'N')

NOME_TABLE_FRAME_QUADRO = 'quadro_coordenadas'

MENSAGEM_LAYOUT_AUSENTE = (
    'Layout "{layout}" (Table Frame "{table_frame}") ainda não existe no '
    'project_layout.aprx desta ferramenta. Crie os layouts no ArcGIS Pro '
    'conforme layout/LEIA-ME_LAYOUTS.txt (T0.2) antes de gerar o quadro em PDF.'
)


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


def exportar_csv_de_feicao(feicao_segmentos, path):
    """
    Wrapper ArcPy: lê a feição final de segmentos (saída de
    `formatar_tabela_atributos.formatar_tabela_atributos` /
    `pipeline_perimetro.montar_tabela_segmentos_de_vertices`) e exporta o
    CSV do quadro de coordenadas.

    Args:
        feicao_segmentos: caminho da feição/tabela com os campos de, para,
            azimute, distancia, E, N, confrontantes.
        path: caminho do arquivo `.csv` de saída.

    Returns:
        os.PathLike: o próprio `path`.

    Raises:
        RuntimeError: se ArcPy não estiver disponível neste ambiente.
    """
    if arcpy is None:
        raise RuntimeError('arcpy não disponível neste ambiente.')

    campos = ['de', 'azimute', 'distancia', 'E', 'N', 'confrontantes']
    segmentos = []
    with arcpy.da.SearchCursor(feicao_segmentos, campos) as cursor:
        for de, azimute, distancia, e_coord, n_coord, confrontantes in cursor:
            segmentos.append(
                {
                    'de': de,
                    'confrontante': confrontantes or '',
                    'azimute': azimute,
                    'distancia_m': distancia,
                    'E': e_coord,
                    'N': n_coord,
                }
            )

    return exportar_csv(segmentos, path)


def preencher_layout_quadro(layout, feicao_segmentos, out_pdf, campos=None):
    """
    Configura o Table Frame `quadro_coordenadas` do layout
    `Layout_Quadro_Coordenadas_A4` com a feição final de segmentos e
    exporta o PDF da folha.

    Args:
        layout: objeto `arcpy._mp.Layout` já carregado (ver
            `gerar_planta_perimetro._obter_layout` para o padrão de busca).
        feicao_segmentos: caminho da feição/tabela final de segmentos.
        out_pdf: caminho do PDF de saída desta folha (scratch).
        campos: dict opcional {nome_campo: rótulo}; default usa os nomes
            do quadro oficial (de, confrontantes, azimute, distancia, E, N).

    Returns:
        os.PathLike: caminho do PDF exportado (`out_pdf`).

    Raises:
        RuntimeError: se ArcPy não estiver disponível, ou se o Table Frame
            `quadro_coordenadas` não existir no layout (layouts T0.2
            ainda não criados — ver layout/LEIA-ME_LAYOUTS.txt).
    """
    if arcpy is None:
        raise RuntimeError('arcpy não disponível neste ambiente.')

    campos = campos or {
        'de': 'De',
        'confrontantes': 'Confrontante',
        'azimute': 'Azimute',
        'distancia': 'Distancia (m)',
        'E': 'E',
        'N': 'N',
    }

    tabelas = layout.listElements(
        element_type='TABLEFRAME_ELEMENT', wildcard=NOME_TABLE_FRAME_QUADRO
    )
    if not tabelas:
        raise RuntimeError(
            MENSAGEM_LAYOUT_AUSENTE.format(
                layout=NOME_LAYOUT_QUADRO, table_frame=NOME_TABLE_FRAME_QUADRO
            )
        )

    tabela = tabelas[0]
    tabela.table = feicao_segmentos
    tabela.fields = list(campos.keys())

    cim_tabela = tabela.getDefinition('V3')
    for field in getattr(cim_tabela, 'fields', []) or []:
        if field.name in campos:
            field.displayName = campos[field.name]
    tabela.setDefinition(cim_tabela)

    return exportar_pdf_layout(layout, out_pdf)
