#-*- coding: utf-8 -*-

import os
import arcpy

def confrontantes(
    in_feature: os.PathLike,
    lote: str,
    lote_features: os.PathLike,
    eixo_viario: os.PathLike
) -> None:
    """
    Função para criar os confrontantes na tabela de atributos, função faz alterações na feature class de entrada.

    -----
    Args:
        in_feature(os.PathLike):
            Caminho para o shapefile de entrada.
        lote(str):
            Lote para o qual os confrontantes serão criados.
        lote_features(os.PathLike):
            Caminho para o shapefile de entrada dos lotes.
        eixo_viario(os.PathLike):
            Caminho para o shapefile de entrada dos eixos viários.

    -----
    Returns:
        None
    """
    
    #Confrontantes de lotes
    mid_point = arcpy.FeatureVerticesToPoints_management(
        in_features=in_feature,
        out_feature_class='mid_point',
        point_location='MID'
    )

    buffer = arcpy.PairwiseBuffer_analysis(
        in_features=mid_point,
        out_feature_class='buffer_mid_point',
        buffer_distance_or_field='1 METERS',
        dissolve_option='NONE',
        method='PLANAR'
    )

    intersect = arcpy.PairwiseIntersect_analysis(
        in_features=[
            buffer,
            lote_features
        ],
        out_feature_class='intersect_lote'
    )

    select_attr = arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=intersect,
        selection_type='NEW_SELECTION',
        where_clause=f'lote = \'{lote}\''
    )

    arcpy.DeleteRows_management(
        in_rows=select_attr
    )

    arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=intersect,
        selection_type='CLEAR_SELECTION'
    )

    arcpy.JoinField_management(
        in_data=in_feature,
        in_field='OBJECTID',
        join_table=intersect,
        join_field='ORIG_FID',
        fields=[
            'lote'
        ]
    )

    #Confrontantes de eixos viários
    arcpy.Near_analysis(
        in_features=mid_point,
        near_features=eixo_viario,
        method='PLANAR',
        distance_unit='Meters'
    )

    arcpy.JoinField_management(
        in_data=mid_point,
        in_field='NEAR_FID',
        join_table=eixo_viario,
        join_field='OBJECTID',
        fields=[
            'logradouro'
        ]
    )

    select_null_lote = arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=in_feature,
        selection_type='NEW_SELECTION',
        where_clause='lote IS NULL'
    )

    arcpy.JoinField_management(
        in_data=select_null_lote,
        in_field='OBJECTID',
        join_table=mid_point,
        join_field='ORIG_FID',
        fields=[
            'logradouro'
        ]
    )

    arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=in_feature,
        selection_type='CLEAR_SELECTION'
    )

    #Estruturação da coluna de confrontantes
    arcpy.AddField_management(
        in_table=in_feature,
        field_name='confrontantes',
        field_type='TEXT',
        field_alias='confrontantes'
    )

    arcpy.CalculateFields_management(
        in_table=in_feature,
        expression_type='PYTHON3',
        fields=[
            ['confrontantes', '\'Lote \' +str(!lote!)', 'lote IS NOT NULL'],
            ['confrontantes', '!logradouro!', 'lote IS NULL']
        ]
    )

    arcpy.DeleteField_management(
        in_table=in_feature,
        drop_field=[
            'lote',
            'logradouro'
        ]
    )

    #eixo viario para o layout
    

# confrontantes('Lote_vertices_PointsToLine', '13','Lote', 'Eixo_viario')