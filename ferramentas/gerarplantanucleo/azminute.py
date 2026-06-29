# -*- coding: utf-8 -*-

import math

import arcpy


def az_quad(delta_x: float, delta_y: float) -> float:
    az = math.degrees(math.atan2(delta_x, delta_y))
    if az < 0:
        az = 360 + az
    return az


def azimute_grau_minuto_segundo(az: float) -> str:
    graus = int(az)
    minutos_flutuantes = (az - graus) * 60
    minutos = int(minutos_flutuantes)
    segundos = round((minutos_flutuantes - minutos) * 60, 2)
    return f'{graus}° {minutos}′ {segundos:.2f}″'


def azimute(feicao_entrada: str) -> None:
    arcpy.AddFields_management(
        in_table=feicao_entrada,
        field_description=[
            ['E', 'DOUBLE', 'E'],
            ['N', 'DOUBLE', 'N'],
            ['azimute', 'TEXT', 'azimute']
        ]
    )

    with arcpy.da.SearchCursor(feicao_entrada, ['OBJECTID', 'SHAPE@X', 'SHAPE@Y']) as cursor:
        vertices = sorted([(row[0], row[1], row[2]) for row in cursor], key=lambda item: item[0])

    if not vertices:
        return

    indice_por_oid = {vertice[0]: indice for indice, vertice in enumerate(vertices)}

    with arcpy.da.UpdateCursor(feicao_entrada, ['OBJECTID', 'E', 'N', 'azimute']) as cursor:
        for row in cursor:
            indice = indice_por_oid[row[0]]
            atual = vertices[indice]
            proximo = vertices[(indice + 1) % len(vertices)]

            row[1] = round(atual[1], 4)
            row[2] = round(atual[2], 4)
            row[3] = azimute_grau_minuto_segundo(
                az_quad(
                    delta_x=proximo[1] - atual[1],
                    delta_y=proximo[2] - atual[2]
                )
            )
            cursor.updateRow(row)
