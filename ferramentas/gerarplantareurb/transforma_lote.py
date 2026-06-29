# -*- coding: utf-8 -*-

import os
import arcpy

def transforma_lote(
    lote_selecionado: os.PathLike
) -> tuple[os.PathLike, os.PathLike]:
    """
    Responsável por transformar o lote em linha e vertices em pontos.

    -------
    Args:
        lote_selecionado(os.PathLike):
            Caminho para o shapefile do lote selecionado.

    -------
    Returns:
        tuple[os.PathLike, os.PathLike]:
            Tupla contendo o caminho para o shapefile do lote transformado em linha e o caminho para o shapefile dos vertices transformados em pontos.
    """
    divisas_lote = arcpy.FeatureToLine_management(
        in_features=lote_selecionado,
        out_feature_class='divisas_lote'
    )

    vertices_lote = arcpy.FeatureVerticesToPoints_management(
        in_features=divisas_lote,
        out_feature_class='vertices_lote',
        point_location='ALL'
    )

    return divisas_lote, vertices_lote