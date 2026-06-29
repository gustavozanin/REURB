# -*- coding: utf-8 -*-

import os
import arcpy

from caminho_camadas import quadra_camada

def exporta_camadas_para_layout(
    confrontantes_lote: os.PathLike,
    n_reurb_coletivo: int,
    n_quadra: int,
    lote: os.PathLike,
    eixo_viario: os.PathLike
) -> tuple[os.PathLike, os.PathLike]:
    """
    Exporta as camadas para o layout

    -------
    Args:
        confrontantes_lote(os.PathLike):
            Caminho para o shapefile dos confrontantes do lote.
        n_reurb_coletivo(int):
            Número do REURB coletivo.
        n_quadra(int):
            Número da quadra.
        lote(os.PathLike):
            Caminho para o shapefile do lote.
        eixo_viario(os.PathLike):
            Caminho para o shapefile do eixo viario.

    -------
    Returns:
        tuple[os.PathLike, os.PathLike]:
            Tupla contendo o caminho para o shapefile do eixo viario e o caminho para o shapefile do lote.
    """

    select_eixo_viario = arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=confrontantes_lote,
        selection_type='NEW_SELECTION',
        where_clause='confrontantes NOT LIKE \'Lote%\''
    )

    eixos = list()

    with arcpy.da.SearchCursor(select_eixo_viario, ['confrontantes']) as search_cursor:
        for row in search_cursor:
            eixos.append(row[0])

    if len(eixos) == 1:
        eixo_viario_layout = arcpy.Select_analysis(
        in_features=eixo_viario,
        out_feature_class='eixo_viario_layout',
        where_clause=f'logradouro = \'{eixos[0]}\''
    )
    else:
        eixo_viario_layout = arcpy.Select_analysis(
            in_features=eixo_viario,
            out_feature_class='eixo_viario_layout',
            where_clause=f'logradouro IN {tuple(eixos)}'
        )

    lotes_layout = arcpy.Select_analysis(
        in_features=lote,
        out_feature_class='lotes_layout',
        where_clause=f'n_coletivo = \'{n_reurb_coletivo}\' AND quadra = {n_quadra}'
    )

    return lotes_layout, eixo_viario_layout