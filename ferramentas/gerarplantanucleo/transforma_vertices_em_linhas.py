# -*- coding: utf-8 -*-

import os
import uuid

import arcpy


def nome_vertice(indice: int) -> str:
    return f'P-{indice:02d}'


def transforma_vertices_em_linhas(vertices_bairro: os.PathLike) -> os.PathLike:
    desc = arcpy.Describe(vertices_bairro)
    spatial_reference = desc.spatialReference

    with arcpy.da.SearchCursor(vertices_bairro, ['OBJECTID', 'SHAPE@', 'E', 'N', 'azimute']) as cursor:
        vertices = sorted([row for row in cursor], key=lambda row: row[0])

    if not vertices:
        raise ValueError('Nenhum vertice encontrado para gerar confrontantes.')

    nomes_campos_vertices = [field.name for field in arcpy.ListFields(vertices_bairro)]
    if 'vertices' not in nomes_campos_vertices:
        arcpy.AddField_management(
            in_table=vertices_bairro,
            field_name='vertices',
            field_type='TEXT'
        )
    if 'rotulo' not in nomes_campos_vertices:
        arcpy.AddField_management(
            in_table=vertices_bairro,
            field_name='rotulo',
            field_type='TEXT'
        )

    indice_por_oid = {row[0]: indice + 1 for indice, row in enumerate(vertices)}
    with arcpy.da.UpdateCursor(vertices_bairro, ['OBJECTID', 'vertices', 'rotulo']) as cursor:
        for row in cursor:
            rotulo = nome_vertice(indice_por_oid[row[0]])
            row[1] = rotulo
            row[2] = rotulo
            cursor.updateRow(row)

    confrontantes_bairro = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name=f'confrontantes_bairro_{uuid.uuid4().hex[:8]}',
        geometry_type='POLYLINE',
        spatial_reference=spatial_reference,
        has_m='DISABLED',
        has_z='DISABLED'
    )

    arcpy.AddField_management(confrontantes_bairro, 'E', 'DOUBLE', field_precision=18, field_scale=4, field_alias='E')
    arcpy.AddField_management(confrontantes_bairro, 'N', 'DOUBLE', field_precision=18, field_scale=4, field_alias='N')
    arcpy.AddField_management(confrontantes_bairro, 'azimute', 'TEXT', field_alias='azimute')
    arcpy.AddField_management(confrontantes_bairro, 'distancia', 'DOUBLE', field_precision=18, field_scale=4, field_alias='distancia')
    arcpy.AddField_management(confrontantes_bairro, 'de', 'TEXT', field_alias='de')
    arcpy.AddField_management(confrontantes_bairro, 'para', 'TEXT', field_alias='para')
    arcpy.AddField_management(confrontantes_bairro, 'confrontantes', 'TEXT', field_alias='confrontantes')

    campos = ['SHAPE@', 'E', 'N', 'azimute', 'distancia', 'de', 'para', 'confrontantes']
    with arcpy.da.InsertCursor(confrontantes_bairro, campos) as cursor:
        for indice, vertice in enumerate(vertices):
            proximo = vertices[(indice + 1) % len(vertices)]
            linha = arcpy.Polyline(
                arcpy.Array([vertice[1].firstPoint, proximo[1].firstPoint]),
                spatial_reference
            )
            cursor.insertRow([
                linha,
                round(float(vertice[2]), 4),
                round(float(vertice[3]), 4),
                vertice[4],
                round(float(linha.length), 4),
                nome_vertice(indice + 1),
                nome_vertice((indice + 1) % len(vertices) + 1),
                ''
            ])

    arcpy.AddMessage(f'Segmentos exportados para o quadro de coordenadas: {len(vertices)}')
    return confrontantes_bairro
