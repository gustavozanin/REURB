# -*- coding: utf-8 -*-

import os
import arcpy

def exporta_camadas_para_layout(
    n_reurb_coletivo: str,
    bairro_feicoes: os.PathLike
) -> os.PathLike:
    """
    Exporta as camadas para o layout

    -------
    Args:
        confrontantes_bairro(os.PathLike):
            Caminho para a camada dos confrontantes do bairro.
        n_reurb_coletivo(str):
            Número do REURB coletivo.
        bairro_feicoes(os.PathLike):
            Caminho para a camada das feições do bairro.

    -------
    Returns:
        os.PathLike:
            Caminho para a camada do bairro layout.
    """

    bairro_layout = arcpy.Select_analysis(
        in_features=bairro_feicoes,
        out_feature_class='bairro_layout',
        where_clause=f'n_coletivo = \'{n_reurb_coletivo}\''
    )

    return bairro_layout