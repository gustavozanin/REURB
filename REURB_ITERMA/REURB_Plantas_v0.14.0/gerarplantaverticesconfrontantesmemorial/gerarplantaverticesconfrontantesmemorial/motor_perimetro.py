# -*- coding: utf-8 -*-
"""Motor geométrico auditável para perímetros SIRGAS 2000 / UTM."""

import math
import os
import arcpy
from azimute_utm import azimute_gms, azimute_graus_decimais
from constantes import TOLERANCIA_DIVERGENCIA_AREA_M2
from linearizar_arcos import (
    pontos_controle_de_geometria,
    tem_curvas,
)


def _rings(geometry):
    for part_index, part in enumerate(geometry, 1):
        ring, ring_index = [], 0
        for point in part:
            if point is None:
                if ring:
                    ring_index += 1
                    yield part_index, ring_index, ring
                    ring = []
            else:
                ring.append(point)
        if ring:
            yield part_index, ring_index + 1, ring


def _same(a, b, tolerance=0.001):
    return abs(a.X - b.X) <= tolerance and abs(a.Y - b.Y) <= tolerance


def _signed_ring_area(points):
    """Área algébrica do anel formado pelos mesmos segmentos do memorial."""
    return 0.5 * sum(
        start.X * end.Y - end.X * start.Y
        for start, end in zip(points, points[1:] + points[:1])
    )


def _create_outputs(sr):
    vertices = os.path.join(arcpy.env.scratchGDB, "vertices_perimetro")
    segments = os.path.join(arcpy.env.scratchGDB, "segmentos_perimetro")
    for path in (vertices, segments):
        if arcpy.Exists(path):
            arcpy.management.Delete(path)
    arcpy.management.CreateFeatureclass(arcpy.env.scratchGDB, "vertices_perimetro", "POINT", spatial_reference=sr)
    arcpy.management.AddFields(vertices, [
        ["vertices", "TEXT", "Vértice", 20], ["parte_id", "LONG", "Parte"],
        ["anel_id", "LONG", "Anel"], ["ordem", "LONG", "Ordem"],
        ["E", "DOUBLE", "Coord. E"], ["N", "DOUBLE", "Coord. N"],
        ["azimute", "TEXT", "Azimute", 30],
    ])
    arcpy.management.CreateFeatureclass(arcpy.env.scratchGDB, "segmentos_perimetro", "POLYLINE", spatial_reference=sr)
    arcpy.management.AddFields(segments, [
        ["de", "TEXT", "De", 20], ["para", "TEXT", "Para", 20],
        ["parte_id", "LONG", "Parte"], ["anel_id", "LONG", "Anel"],
        ["ordem", "LONG", "Ordem"], ["azimute", "TEXT", "Azimute", 30],
        ["distancia", "DOUBLE", "Distância (m)"], ["E", "DOUBLE", "Coord. E"],
        ["N", "DOUBLE", "Coord. N"],
    ])
    return vertices, segments


def gerar_vertices_segmentos(feicao_perimetro):
    count = int(arcpy.management.GetCount(feicao_perimetro)[0])
    if count != 1:
        raise ValueError(
            "O processo deve selecionar exatamente uma feição de perímetro; "
            f"foram encontradas {count}. Corrija duplicidades antes da emissão."
        )
    with arcpy.da.SearchCursor(feicao_perimetro, ["SHAPE@"]) as cursor:
        geometry = next(cursor)[0]
    if not geometry or int(getattr(geometry, "pointCount", 0)) < 1:
        raise ValueError("A feição selecionada não possui geometria válida.")
    sr = geometry.spatialReference
    if not sr or sr.type != "Projected":
        raise ValueError("O motor de perímetro exige geometria projetada em UTM.")
    geometria_original = geometry
    if tem_curvas(geometry):
        arcpy.AddMessage(
            'Perímetro com arcos: memorial, planta e quadro usam os '
            'vértices do projeto. Nenhum ponto extra é inserido na curva.'
        )
    vertices_fc, segments_fc = _create_outputs(sr)
    rings = []
    for ring_id, xy in enumerate(pontos_controle_de_geometria(geometry), 1):
        points = [arcpy.Point(x, y) for x, y in xy]
        if len(points) > 1 and _same(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            raise ValueError(
                f"Parte 1, anel {ring_id} possui menos de 3 vértices."
            )
        rings.append((1, ring_id, points))
    if not rings:
        raise ValueError("Nenhum anel válido foi encontrado no perímetro.")

    v_fields = ["SHAPE@", "vertices", "parte_id", "anel_id", "ordem", "E", "N", "azimute"]
    s_fields = ["SHAPE@", "de", "para", "parte_id", "anel_id", "ordem", "azimute", "distancia", "E", "N"]
    vertex_number, segment_count, distance_sum = 1, 0, 0.0
    signed_area_sum = 0.0
    vertex_rows, segment_rows = [], []
    for part_id, ring_id, points in rings:
        signed_area_sum += _signed_ring_area(points)
        names = [f"P-{n:03d}" for n in range(vertex_number, vertex_number + len(points))]
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            dx, dy = end.X - start.X, end.Y - start.Y
            distance = math.hypot(dx, dy)
            if distance < 0.005:
                raise ValueError(f"Segmento nulo ou inferior a 5 mm em {names[index]}.")
            azimuth = azimute_gms(azimute_graus_decimais(dx, dy))
            line = arcpy.Polyline(arcpy.Array([start, end]), sr)
            vertex_rows.append([arcpy.PointGeometry(start, sr), names[index], part_id, ring_id, index + 1, start.X, start.Y, azimuth])
            segment_rows.append([line, names[index], names[(index + 1) % len(points)], part_id, ring_id, index + 1, azimuth, round(distance, 4), start.X, start.Y])
            segment_count += 1
            distance_sum += distance
        vertex_number += len(points)
    with arcpy.da.InsertCursor(vertices_fc, v_fields) as cursor:
        for row in vertex_rows:
            cursor.insertRow(row)
    with arcpy.da.InsertCursor(segments_fc, s_fields) as cursor:
        for row in segment_rows:
            cursor.insertRow(row)
    coordinate_area = abs(signed_area_sum)
    geometry_area = abs(float(geometria_original.area))
    geometry_perimeter = float(geometria_original.length)
    if abs(geometry_area - coordinate_area) > TOLERANCIA_DIVERGENCIA_AREA_M2:
        arcpy.AddWarning(
            'A área da poligonal descrita difere da área da geometria do '
            f'bairro em {geometry_area - coordinate_area:.2f} m² '
            f'({coordinate_area:.2f} m² descritos contra {geometry_area:.2f} '
            'm² na geometria). Confira o perímetro na origem antes de levar '
            'o documento ao registro.'
        )
    audit = {
        "quantidadeFeicoes": count,
        "quantidadePartes": len({r[0] for r in rings}),
        "quantidadeAneis": len(rings),
        "quantidadeVertices": vertex_number - 1,
        "quantidadeSegmentos": segment_count,
        "verticesDeArcosLinearizados": 0,
        "desvioMaximoLinearizacaoArcosM": 0,
        "somaDistanciasM": round(distance_sum, 4),
        "perimetroCoordenadasM": round(distance_sum, 4),
        "areaCoordenadasM2": round(coordinate_area, 4),
        "perimetroGeometriaOriginalM": round(geometry_perimeter, 4),
        "areaGeometriaOriginalM2": round(geometry_area, 4),
        "diferencaPerimetroOriginalM": round(geometry_perimeter - distance_sum, 4),
        "diferencaAreaOriginalM2": round(geometry_area - coordinate_area, 4),
        # Mantidos por compatibilidade com consumidores anteriores.
        "perimetroGeometriaM": round(geometry_perimeter, 4),
        "diferencaFechamentoM": round(abs(distance_sum - geometry_perimeter), 4),
        "wkid": sr.factoryCode,
        "sistemaReferencia": sr.name,
    }
    return segments_fc, vertices_fc, audit
