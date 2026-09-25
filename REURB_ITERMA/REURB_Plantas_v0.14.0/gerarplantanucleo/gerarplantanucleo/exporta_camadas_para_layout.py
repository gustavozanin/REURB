# -*- coding: utf-8 -*-

import os
import arcpy


def __selecionar_por_atributo_e_centroide(
    feicoes: os.PathLike,
    bairro_layout: os.PathLike,
    where_clause: str,
    out_feature_class: str
) -> os.PathLike:
    """
    Filtra feições por atributo e depois mantém as que intersectam
    o perímetro do bairro (quadra/lote na borda não some).
    """
    scratch_gdb = arcpy.env.scratchGDB
    saida = os.path.join(scratch_gdb, out_feature_class)
    feicoes_attr = os.path.join(scratch_gdb, f'{out_feature_class}_attr')

    arcpy.Select_analysis(
        in_features=feicoes,
        out_feature_class=feicoes_attr,
        where_clause=where_clause
    )

    feicoes_layer = arcpy.MakeFeatureLayer_management(
        in_features=feicoes_attr,
        out_layer=f'{out_feature_class}_layer'
    )

    arcpy.SelectLayerByLocation_management(
        in_layer=feicoes_layer,
        overlap_type='INTERSECT',
        select_features=bairro_layout,
        selection_type='NEW_SELECTION'
    )

    arcpy.CopyFeatures_management(
        in_features=feicoes_layer,
        out_feature_class=saida
    )

    return saida


def exporta_camadas_para_layout(
    n_reurb_coletivo: str,
    bairro_feicoes: os.PathLike,
    quadra_feicoes: os.PathLike,
    lote_feicoes: os.PathLike
) -> tuple[os.PathLike, os.PathLike, os.PathLike]:
    """
    Exporta bairro, quadras e lotes para o layout.
    """
    where_reurb = f"n_coletivo = '{n_reurb_coletivo}'"

    bairro_layout = arcpy.Select_analysis(
        in_features=bairro_feicoes,
        out_feature_class='bairro_layout',
        where_clause=where_reurb
    )

    quadra_layout = __selecionar_por_atributo_e_centroide(
        feicoes=quadra_feicoes,
        bairro_layout=bairro_layout,
        where_clause=where_reurb,
        out_feature_class='quadra_layout'
    )

    lote_layout = __selecionar_por_atributo_e_centroide(
        feicoes=lote_feicoes,
        bairro_layout=bairro_layout,
        where_clause=where_reurb,
        out_feature_class='lote_layout'
    )

    return bairro_layout, quadra_layout, lote_layout
