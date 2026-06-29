# -*- coding: utf-8 -*-

import os
import arcpy

def formatar_tabela_atributos(
    in_features: os.PathLike
) -> os.PathLike:
    """
    Função para formatar a tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N.

    -----
    Args:
        in_features(os.PathLike):
            Caminho para o shapefile de entrada.

    -----
    Returns:
        os.PathLike:
            Caminho para o shapefile de saída.
    """

    arcpy.AddFields_management(
        in_table=in_features,
        field_description=[
            ['de', 'TEXT', 'de'],
            ['para', 'TEXT', 'para']
        ]
    )

    with arcpy.da.SearchCursor(in_features, ['OBJECTID']) as search_cursor:
        dict_oid = {row[0]: f'P-0{row[0]}' if len(str(row[0])) == 1 else f'P-{row[0]}' for row in search_cursor}
    print(dict_oid)

    with arcpy.da.UpdateCursor(in_features, ['OBJECTID', 'de', 'para']) as update_cursor:
        for row in update_cursor:
            oid = row[0]
            de = row[1]
            para = row[2]

            if oid < list(dict_oid.keys())[-1]:
                row[1] = dict_oid[oid]
                row[2] = dict_oid[oid+1]
                print(f'oid: {oid}, de: {dict_oid[oid]}, para: {dict_oid[oid+1]}')
            else:
                row[1] = dict_oid[oid]
                row[2] = dict_oid[1]
                print(f'oid: {oid}, de: {dict_oid[oid]}, para: {dict_oid[1]}')

            update_cursor.updateRow(row)

    desc = arcpy.Describe(
        value=in_features
    )

    geometry_type = desc.shapeType
    spatial_reference = desc.spatialReference

    confrontantes_lote_final = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name='confrontantes_lote_final',
        has_m='DISABLED',
        has_z='DISABLED',
        geometry_type=geometry_type,
        spatial_reference=spatial_reference
    )

    arcpy.AddFields_management(
        in_table=confrontantes_lote_final,
        field_description=[
            ['de', 'TEXT', 'De'],
            ['para', 'TEXT', 'Para'],
            ['azimute', 'TEXT', 'Azimute'],
            ['distancia', 'DOUBLE', 'Distância (m)'],
            ['E', 'DOUBLE', 'Coord. E (x)'],
            ['N', 'DOUBLE', 'Coord. N (y)'],
            ['confrontantes', 'TEXT', 'Confrontantes']
        ]
    )

    arcpy.Append_management(
        inputs=in_features,
        target=confrontantes_lote_final,
        schema_type='NO_TEST'
    )

    return confrontantes_lote_final