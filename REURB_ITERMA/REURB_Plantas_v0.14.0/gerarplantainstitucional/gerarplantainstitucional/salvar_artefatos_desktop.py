# -*- coding: utf-8 -*-

"""Copia PDF unificado, CSV do quadro e ZIP do shapefile para a pasta
escolhida pelo analista, com os nomes finais desta ferramenta.

Adaptado de `gerarplantanucleo/gerarplantanucleo/salvar_artefatos_desktop.py`
para os três artefatos desta ferramenta (nomes fixos, ver design.md):

    - `planta_vertices_memorial_{n}.pdf`
    - `quadro_coordenadas_{n}.csv`
    - `shape_vertices_{n}.zip`

Qualquer um dos três pode ser omitido (`None`) — usado quando o PDF ainda
não pôde ser gerado (layouts pendentes, ver `layout/LEIA-ME_LAYOUTS.txt`)
mas CSV/ZIP já estão prontos. Regra "pronto" desta ferramenta: CSV e ZIP
são salvos sempre que a geometria roda; o PDF só entra quando os layouts
existem; `pronto=True` (ver `fluxo_geracao.py`) exige os três.
"""

import os
import shutil
import arcpy


def _copiar_sem_sobrescrever(origem, destino):
    if os.path.exists(destino):
        raise ValueError(
            'Já existe um arquivo neste caminho e a ferramenta não '
            'sobrescreve: {}'.format(destino)
        )
    pasta = os.path.dirname(destino)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    shutil.copy2(origem, destino)


def salvar_artefatos_memorial(
    pasta_saida: os.PathLike,
    numero_reurb_coletivo: str,
    pdf_unificado: os.PathLike = None,
    csv_quadro: os.PathLike = None,
    zip_shapefile: os.PathLike = None,
) -> dict:
    """
    Copia para `pasta_saida` os artefatos informados (os que forem
    `None` são simplesmente ignorados), com os nomes finais desta
    ferramenta, e devolve os caminhos finais.

    Args:
        pasta_saida: pasta de saída escolhida pelo analista.
        numero_reurb_coletivo: usado para montar o sufixo dos nomes de
            arquivo (`/` vira `_`).
        pdf_unificado: caminho do PDF unificado (scratch), ou `None`
            se ainda não foi possível gerar (layouts pendentes).
        csv_quadro: caminho do CSV do quadro de coordenadas (scratch).
        zip_shapefile: caminho do ZIP do shapefile (scratch).

    Returns:
        dict com chaves `pdf`, `csv`, `zip` (string vazia se o artefato
        correspondente não foi informado) e `numeroProcessoColetivo`.

    Raises:
        ValueError: se `pasta_saida` não foi informada.
    """
    if not pasta_saida:
        raise ValueError('Pasta de saída não informada')

    os.makedirs(pasta_saida, exist_ok=True)
    slug = numero_reurb_coletivo.replace('/', '_')

    artefatos = {
        'pdf': '',
        'csv': '',
        'zip': '',
        'numeroProcessoColetivo': numero_reurb_coletivo,
    }

    if pdf_unificado:
        destino = os.path.join(pasta_saida, f'planta_vertices_memorial_{slug}.pdf')
        _copiar_sem_sobrescrever(pdf_unificado, destino)
        arcpy.AddMessage(f'PDF salvo em: {destino}')
        artefatos['pdf'] = destino

    if csv_quadro:
        destino = os.path.join(pasta_saida, f'quadro_coordenadas_{slug}.csv')
        _copiar_sem_sobrescrever(csv_quadro, destino)
        arcpy.AddMessage(f'CSV salvo em: {destino}')
        artefatos['csv'] = destino

    if zip_shapefile:
        destino = os.path.join(pasta_saida, f'shape_vertices_{slug}.zip')
        _copiar_sem_sobrescrever(zip_shapefile, destino)
        arcpy.AddMessage(f'Shapefile ZIP salvo em: {destino}')
        artefatos['zip'] = destino

    return artefatos


def salvar_artefatos_institucional(
    pasta_saida: os.PathLike,
    numero_reurb_coletivo: str,
    quadra,
    lote,
    pdf_unificado: os.PathLike = None,
    csv_quadro: os.PathLike = None,
    zip_shapefile: os.PathLike = None,
) -> dict:
    """Copia artefatos com prefixo planta_institucional_…_Q…_L…."""
    if not pasta_saida:
        raise ValueError('Pasta de saída não informada')

    os.makedirs(pasta_saida, exist_ok=True)
    slug = (
        f'{numero_reurb_coletivo.replace("/", "_")}'
        f'_Q{quadra}_L{lote}'
    )

    artefatos = {
        'pdf': '',
        'csv': '',
        'zip': '',
        'numeroProcessoColetivo': numero_reurb_coletivo,
        'quadra': quadra,
        'lote': lote,
    }

    if pdf_unificado:
        destino = os.path.join(pasta_saida, f'planta_institucional_{slug}.pdf')
        _copiar_sem_sobrescrever(pdf_unificado, destino)
        arcpy.AddMessage(f'PDF salvo em: {destino}')
        artefatos['pdf'] = destino

    if csv_quadro:
        destino = os.path.join(pasta_saida, f'quadro_institucional_{slug}.csv')
        _copiar_sem_sobrescrever(csv_quadro, destino)
        arcpy.AddMessage(f'CSV salvo em: {destino}')
        artefatos['csv'] = destino

    if zip_shapefile:
        destino = os.path.join(pasta_saida, f'shape_institucional_{slug}.zip')
        _copiar_sem_sobrescrever(zip_shapefile, destino)
        arcpy.AddMessage(f'Shapefile ZIP salvo em: {destino}')
        artefatos['zip'] = destino

    return artefatos
