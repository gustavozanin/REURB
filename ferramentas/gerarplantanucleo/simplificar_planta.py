# -*- coding: utf-8 -*-

import math
import uuid

import arcpy

from azminute import az_quad, azimute_grau_minuto_segundo


MAX_VERTICES_PLANTA = 60


def _distancia_ponto_segmento(ponto, inicio, fim):
    px, py = ponto
    ax, ay = inicio
    bx, by = fim
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _rdp(pontos, tolerancia):
    if len(pontos) <= 2:
        return pontos

    inicio = pontos[0]
    fim = pontos[-1]
    maior_distancia = -1
    indice = 0

    for i in range(1, len(pontos) - 1):
        distancia = _distancia_ponto_segmento(pontos[i], inicio, fim)
        if distancia > maior_distancia:
            maior_distancia = distancia
            indice = i

    if maior_distancia > tolerancia:
        esquerda = _rdp(pontos[:indice + 1], tolerancia)
        direita = _rdp(pontos[indice:], tolerancia)
        return esquerda[:-1] + direita

    return [inicio, fim]


def _deflexao_graus(anterior, ponto, proximo):
    v1x = anterior[0] - ponto[0]
    v1y = anterior[1] - ponto[1]
    v2x = proximo[0] - ponto[0]
    v2y = proximo[1] - ponto[1]
    n1 = math.hypot(v1x, v1y)
    n2 = math.hypot(v2x, v2y)
    if n1 == 0 or n2 == 0:
        return 0
    cosseno = ((v1x * v2x) + (v1y * v2y)) / (n1 * n2)
    cosseno = max(-1, min(1, cosseno))
    angulo = math.degrees(math.acos(cosseno))
    return abs(180 - angulo)


def _reduzir_por_importancia(pontos, max_vertices):
    if len(pontos) <= max_vertices:
        return pontos

    pontuados = []
    total = len(pontos)
    for indice, ponto in enumerate(pontos):
        anterior = pontos[indice - 1]
        proximo = pontos[(indice + 1) % total]
        deflexao = _deflexao_graus(anterior, ponto, proximo)
        dist_local = min(
            math.hypot(ponto[0] - anterior[0], ponto[1] - anterior[1]),
            math.hypot(ponto[0] - proximo[0], ponto[1] - proximo[1])
        )
        pontuados.append((indice, deflexao * 1000 + dist_local))

    manter = {indice for indice, _ in sorted(pontuados, key=lambda item: item[1], reverse=True)[:max_vertices]}
    return [ponto for indice, ponto in enumerate(pontos) if indice in manter]


def _simplificar_fechado(pontos, max_vertices=MAX_VERTICES_PLANTA):
    if len(pontos) <= max_vertices:
        return pontos

    centro_x = sum(p[0] for p in pontos) / len(pontos)
    centro_y = sum(p[1] for p in pontos) / len(pontos)
    inicio_indice = max(
        range(len(pontos)),
        key=lambda i: math.hypot(pontos[i][0] - centro_x, pontos[i][1] - centro_y)
    )
    rotacionados = pontos[inicio_indice:] + pontos[:inicio_indice]
    linha_fechada = rotacionados + [rotacionados[0]]

    tolerancia = 0.5
    simplificados = linha_fechada
    while tolerancia <= 100:
        simplificados = _rdp(linha_fechada, tolerancia)
        if simplificados and simplificados[0] == simplificados[-1]:
            simplificados = simplificados[:-1]
        if len(simplificados) <= max_vertices:
            break
        tolerancia *= 1.25

    if len(simplificados) > max_vertices:
        simplificados = _reduzir_por_importancia(simplificados, max_vertices)

    return simplificados


def _nome_vertice(indice):
    return f'P-{indice:02d}'


def criar_vertices_segmentos_simplificados(vertices_bairro, max_vertices=MAX_VERTICES_PLANTA):
    desc = arcpy.Describe(vertices_bairro)
    sr = desc.spatialReference

    with arcpy.da.SearchCursor(vertices_bairro, ['OBJECTID', 'SHAPE@X', 'SHAPE@Y']) as cursor:
        vertices = sorted([(row[0], row[1], row[2]) for row in cursor], key=lambda row: row[0])

    pontos = [(x, y) for _, x, y in vertices]
    pontos_simplificados = _simplificar_fechado(pontos, max_vertices=max_vertices)

    vertices_saida = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name=f'vertices_planta_{uuid.uuid4().hex[:8]}',
        geometry_type='POINT',
        spatial_reference=sr,
        has_m='DISABLED',
        has_z='DISABLED'
    )
    arcpy.AddField_management(vertices_saida, 'E', 'DOUBLE', field_precision=18, field_scale=4)
    arcpy.AddField_management(vertices_saida, 'N', 'DOUBLE', field_precision=18, field_scale=4)
    arcpy.AddField_management(vertices_saida, 'azimute', 'TEXT')
    arcpy.AddField_management(vertices_saida, 'vertices', 'TEXT')
    arcpy.AddField_management(vertices_saida, 'rotulo', 'TEXT')

    with arcpy.da.InsertCursor(vertices_saida, ['SHAPE@', 'E', 'N', 'azimute', 'vertices', 'rotulo']) as cursor:
        for indice, ponto in enumerate(pontos_simplificados):
            proximo = pontos_simplificados[(indice + 1) % len(pontos_simplificados)]
            az = azimute_grau_minuto_segundo(
                az_quad(
                    delta_x=proximo[0] - ponto[0],
                    delta_y=proximo[1] - ponto[1]
                )
            )
            rotulo = _nome_vertice(indice + 1)
            cursor.insertRow([
                arcpy.PointGeometry(arcpy.Point(ponto[0], ponto[1]), sr),
                round(ponto[0], 4),
                round(ponto[1], 4),
                az,
                rotulo,
                rotulo
            ])

    segmentos_saida = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name=f'confrontantes_planta_{uuid.uuid4().hex[:8]}',
        geometry_type='POLYLINE',
        spatial_reference=sr,
        has_m='DISABLED',
        has_z='DISABLED'
    )
    arcpy.AddField_management(segmentos_saida, 'E', 'DOUBLE', field_precision=18, field_scale=4)
    arcpy.AddField_management(segmentos_saida, 'N', 'DOUBLE', field_precision=18, field_scale=4)
    arcpy.AddField_management(segmentos_saida, 'azimute', 'TEXT')
    arcpy.AddField_management(segmentos_saida, 'distancia', 'DOUBLE', field_precision=18, field_scale=4)
    arcpy.AddField_management(segmentos_saida, 'de', 'TEXT')
    arcpy.AddField_management(segmentos_saida, 'para', 'TEXT')
    arcpy.AddField_management(segmentos_saida, 'confrontantes', 'TEXT')

    with arcpy.da.InsertCursor(segmentos_saida, ['SHAPE@', 'E', 'N', 'azimute', 'distancia', 'de', 'para', 'confrontantes']) as cursor:
        for indice, ponto in enumerate(pontos_simplificados):
            proximo = pontos_simplificados[(indice + 1) % len(pontos_simplificados)]
            linha = arcpy.Polyline(
                arcpy.Array([arcpy.Point(ponto[0], ponto[1]), arcpy.Point(proximo[0], proximo[1])]),
                sr
            )
            az = azimute_grau_minuto_segundo(
                az_quad(
                    delta_x=proximo[0] - ponto[0],
                    delta_y=proximo[1] - ponto[1]
                )
            )
            cursor.insertRow([
                linha,
                round(ponto[0], 4),
                round(ponto[1], 4),
                az,
                round(linha.length, 4),
                _nome_vertice(indice + 1),
                _nome_vertice((indice + 1) % len(pontos_simplificados) + 1),
                ''
            ])

    arcpy.AddMessage(
        f'Versao simplificada para a planta: {len(vertices)} vertices completos -> '
        f'{len(pontos_simplificados)} vertices na prancha.'
    )
    return vertices_saida, segmentos_saida
