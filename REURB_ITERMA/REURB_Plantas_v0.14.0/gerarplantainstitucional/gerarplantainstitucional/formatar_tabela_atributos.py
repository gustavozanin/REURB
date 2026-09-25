# -*- coding: utf-8 -*-

import os
import arcpy

def formatar_tabela_atributos(
    feicao_entrada: os.PathLike
) -> os.PathLike:
    """
    Função para formatar a tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N.

    -----
    Args:
        feicao_entrada(os.PathLike):
            Caminho para a camada de entrada.

    -----
    Returns:
        os.PathLike:
            Caminho para a camada de saída.
    """

    existing = {field.name.lower() for field in arcpy.ListFields(feicao_entrada)}
    if not {'de', 'para'}.issubset(existing):
        raise ValueError('A feição de segmentos deve possuir os campos de/para.')

    desc = arcpy.Describe(
        value=feicao_entrada
    )

    geometry_type = desc.shapeType
    spatial_reference = desc.spatialReference

    confrontantes_bairro_final = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name='confrontantes_bairro_final',
        has_m='DISABLED',
        has_z='DISABLED',
        geometry_type=geometry_type,
        spatial_reference=spatial_reference
    )

    arcpy.AddFields_management(
        in_table=confrontantes_bairro_final,
        field_description=[
            ['de', 'TEXT', 'De'],
            ['para', 'TEXT', 'Para'],
            ['azimute', 'TEXT', 'Azimute'],
            ['distancia', 'DOUBLE', 'Distância (m)'],
            ['E', 'DOUBLE', 'Coord. E (x)'],
            ['N', 'DOUBLE', 'Coord. N (y)'],
            ['confrontantes', 'TEXT', 'Confrontantes', 120]
        ]
    )

    arcpy.Append_management(
        inputs=feicao_entrada,
        target=confrontantes_bairro_final,
        schema_type='NO_TEST'
    )

    return confrontantes_bairro_final
