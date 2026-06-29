# -*- coding: utf-8 -*-

import os
import arcpy
from arcpy.management import CalculateGeometryAttributes

def transforma_vertices_em_linhas(
    vertices_lote: os.PathLike
) -> os.PathLike:
    """
    Transformar vertices em linhas

    -------
    Args:
        vertices_lote: os.PathLike
            Caminho para o shapefile dos vertices do lote.

    -------
    Returns:
        os.PathLike:
            Caminho para o shapefile das linhas dos vertices do lote.
    """
    list_fields = ['E', 'N', 'azimute']
    
    confrontantes_lote = arcpy.PointsToLine_management(
        Input_Features=vertices_lote,
        Output_Feature_Class='confrontantes_lote',
        Line_Construction_Method='TWO_POINT',
        Attribute_Source='START',
        Transfer_Fields=list_fields
    )

    for field in list_fields:
        arcpy.AlterField_management(
            in_table=confrontantes_lote,
            field=f'START_{field}',
            new_field_name=field,
            new_field_alias=field
        )

    arcpy.AddField_management(
        in_table=confrontantes_lote,
        field_name='distancia',
        field_type='DOUBLE',
        field_precision=2,
        field_scale=2
    )

    arcpy.CalculateGeometryAttributes_management(
        in_features=confrontantes_lote,
        geometry_property=[
            ['distancia', 'LENGTH']
        ],
        length_unit='METERS'
    )

    with arcpy.da.UpdateCursor(confrontantes_lote, ['distancia']) as cursor:
        for row in cursor:
            row[0] = round(row[0], 2)
            cursor.updateRow(row)

    cursor = arcpy.da.SearchCursor(vertices_lote, ['OBJECTID'])
    n_vertices = [row[0] for row in cursor]

    select = arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=vertices_lote,
        selection_type='NEW_SELECTION',
        where_clause=f'OBJECTID = {n_vertices[-1]}'
    )
    arcpy.DeleteRows_management(
        in_rows=select
    )

    arcpy.AddField_management(
        in_table=vertices_lote,
        field_name='vertices',
        field_type='TEXT'
    )

    with arcpy.da.UpdateCursor(vertices_lote, ['OBJECTID', 'vertices']) as cursor:
        for row in cursor:
            if len(str(row[0])) == 1:
                row[1] = f'P-0{row[0]}'
            else:
                row[1] = f'P-{row[0]}'

            cursor.updateRow(row)
            # arcpy.CalculateField_management(
            #     in_table=vertices_lote,
            #     field='vertice',
            #     expression=f'\'{vertice}\'',
            #     expression_type='PYTHON3'
            # )

    return confrontantes_lote