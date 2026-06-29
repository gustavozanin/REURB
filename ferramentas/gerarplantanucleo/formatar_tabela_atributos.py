# -*- coding: utf-8 -*-

import os
import uuid

import arcpy
from normalizacao import decimal_texto


def formatar_tabela_atributos(feicao_entrada: os.PathLike, limite_linhas: int = None) -> os.PathLike:
    desc = arcpy.Describe(value=feicao_entrada)

    confrontantes_bairro_final = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name=f'confrontantes_bairro_final_{uuid.uuid4().hex[:8]}',
        has_m='DISABLED',
        has_z='DISABLED',
        geometry_type=desc.shapeType,
        spatial_reference=desc.spatialReference
    )

    arcpy.AddField_management(confrontantes_bairro_final, 'de', 'TEXT', field_alias='De')
    arcpy.AddField_management(confrontantes_bairro_final, 'para', 'TEXT', field_alias='Para')
    arcpy.AddField_management(confrontantes_bairro_final, 'azimute', 'TEXT', field_alias='Azim.')
    arcpy.AddField_management(confrontantes_bairro_final, 'distancia', 'DOUBLE', field_precision=18, field_scale=4, field_alias='Dist.')
    arcpy.AddField_management(confrontantes_bairro_final, 'E', 'DOUBLE', field_precision=18, field_scale=4, field_alias='Coord. E')
    arcpy.AddField_management(confrontantes_bairro_final, 'N', 'DOUBLE', field_precision=18, field_scale=4, field_alias='Coord. N')
    arcpy.AddField_management(confrontantes_bairro_final, 'dist_txt', 'TEXT', field_alias='Dist.')
    arcpy.AddField_management(confrontantes_bairro_final, 'E_txt', 'TEXT', field_alias='Coord. E')
    arcpy.AddField_management(confrontantes_bairro_final, 'N_txt', 'TEXT', field_alias='Coord. N')
    arcpy.AddField_management(confrontantes_bairro_final, 'confrontantes', 'TEXT', field_alias='Confrontantes')

    campos_origem = ['SHAPE@', 'de', 'para', 'azimute', 'distancia', 'E', 'N', 'confrontantes']
    campos_destino = ['SHAPE@', 'de', 'para', 'azimute', 'distancia', 'E', 'N', 'dist_txt', 'E_txt', 'N_txt', 'confrontantes']
    with arcpy.da.SearchCursor(feicao_entrada, campos_origem) as search_cursor:
        with arcpy.da.InsertCursor(confrontantes_bairro_final, campos_destino) as insert_cursor:
            for indice, row in enumerate(search_cursor):
                if limite_linhas is not None and indice >= limite_linhas:
                    break
                row = list(row)
                row[4] = round(float(row[4]), 4) if row[4] not in (None, '') else row[4]
                row[5] = round(float(row[5]), 4) if row[5] not in (None, '') else row[5]
                row[6] = round(float(row[6]), 4) if row[6] not in (None, '') else row[6]
                insert_cursor.insertRow([
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    decimal_texto(row[4]),
                    decimal_texto(row[5]),
                    decimal_texto(row[6]),
                    row[7]
                ])

    quantidade = int(arcpy.management.GetCount(confrontantes_bairro_final)[0])
    if limite_linhas is not None:
        arcpy.AddMessage(f'Linhas no quadro resumido da planta: {quantidade} de ate {limite_linhas}')
    else:
        arcpy.AddMessage(f'Linhas no quadro de coordenadas final: {quantidade}')
    return confrontantes_bairro_final
