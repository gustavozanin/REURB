# -*- coding: utf-8 -*-

import os
import uuid
import arcpy

def _mesmo_ponto(ponto_a, ponto_b) -> bool:
    return ponto_a and ponto_b and ponto_a.X == ponto_b.X and ponto_a.Y == ponto_b.Y

def transforma_feicao(
    feicao_perimetro: os.PathLike
) -> os.PathLike:
    """
    Responsável por transformar a feição de polígono em linha e vertices em pontos.

    -------
    Args:
        feicao_perimetro(os.PathLike):
            Caminho para a camada da feição de polígono.

    -------
    Returns:
        os.PathLike:
            Caminho para a camada dos vertices transformados em pontos.
    """
    desc = arcpy.Describe(feicao_perimetro)
    spatial_reference = desc.spatialReference

    vertices_feicao = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name=f'vertices_feicao_{uuid.uuid4().hex[:8]}',
        geometry_type='POINT',
        spatial_reference=spatial_reference,
        has_m='DISABLED',
        has_z='DISABLED'
    )

    with arcpy.da.InsertCursor(vertices_feicao, ['SHAPE@']) as insert_cursor:
        with arcpy.da.SearchCursor(feicao_perimetro, ['SHAPE@']) as search_cursor:
            for row in search_cursor:
                geometria = row[0]
                for parte in geometria:
                    pontos = [ponto for ponto in parte if ponto]
                    if not pontos:
                        continue

                    if len(pontos) > 1 and _mesmo_ponto(pontos[0], pontos[-1]):
                        pontos = pontos[:-1]

                    for ponto in pontos:
                        insert_cursor.insertRow([arcpy.PointGeometry(ponto, spatial_reference)])

    arcpy.AddMessage(f"Vértices criados sem FeatureVerticesToPoints: {vertices_feicao}")
    return vertices_feicao
