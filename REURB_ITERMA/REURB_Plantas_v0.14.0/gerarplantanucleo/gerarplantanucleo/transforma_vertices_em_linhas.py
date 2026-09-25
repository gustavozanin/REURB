# -*- coding: utf-8 -*-

import os
import arcpy

def transforma_vertices_em_linhas(
    vertices_bairro: os.PathLike
) -> os.PathLike:
    """
    Transformar vertices em linhas

    -------
    Args:
        vertices_bairro: os.PathLike
            Caminho para a camada dos vertices do bairro.

    -------
    Returns:
        os.PathLike:
            Caminho para a camada das linhas dos vertices do bairro.
    """    
    list_fields = ['E', 'N', 'azimute']
    
    confrontantes_bairro = arcpy.PointsToLine_management(
        Input_Features=vertices_bairro,
        Output_Feature_Class='confrontantes_bairro',
        Line_Construction_Method='TWO_POINT',
        Attribute_Source='START',
        Transfer_Fields=list_fields
    )

    for field in list_fields:
        arcpy.AlterField_management(
            in_table=confrontantes_bairro,
            field=f'START_{field}',
            new_field_name=field,
            new_field_alias=field
        )

    arcpy.AddField_management(
        in_table=confrontantes_bairro,
        field_name='distancia',
        field_type='DOUBLE',
        field_precision=2,
        field_scale=2
    )

    arcpy.CalculateGeometryAttributes_management(
        in_features=confrontantes_bairro,
        geometry_property=[
            ['distancia', 'LENGTH']
        ],
        length_unit='METERS'
    )

    with arcpy.da.UpdateCursor(confrontantes_bairro, ['distancia']) as cursor:
        for row in cursor:
            row[0] = round(row[0], 2)
            cursor.updateRow(row)

    with arcpy.da.SearchCursor(vertices_bairro, ['OBJECTID']) as cursor:
        n_vertices = [row[0] for row in cursor]

    select = arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=vertices_bairro,
        selection_type='NEW_SELECTION',
        where_clause=f'OBJECTID = {n_vertices[-1]}'
    )
    arcpy.DeleteRows_management(
        in_rows=select
    )

    arcpy.AddField_management(
        in_table=vertices_bairro,
        field_name='vertices',
        field_type='TEXT'
    )

    # Três dígitos, iguais aos do memorial e do quadro: quem confere no
    # registro cruza a planta com as duas tabelas pelo nome do vértice.
    with arcpy.da.UpdateCursor(vertices_bairro, ['OBJECTID', 'vertices']) as cursor:
        for row in cursor:
            row[1] = f'P-{row[0]:03d}'
            cursor.updateRow(row)
            # arcpy.CalculateField_management(
            #     in_table=vertices_lote,
            #     field='vertice',
            #     expression=f'\'{vertice}\'',
            #     expression_type='PYTHON3'
            # )

    return confrontantes_bairro