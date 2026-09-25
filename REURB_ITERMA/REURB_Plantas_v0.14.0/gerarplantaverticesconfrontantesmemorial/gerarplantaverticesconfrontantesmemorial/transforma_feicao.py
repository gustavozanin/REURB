# -*- coding: utf-8 -*-

"""Converte polígono em vértices (pontos) sem ferramentas Advanced."""

import os
import arcpy


def _ponto_igual(p1, p2, tol=1e-8):
    if p1 is None or p2 is None:
        return False
    return abs(p1.X - p2.X) <= tol and abs(p1.Y - p2.Y) <= tol


def transforma_feicao(
    feicao_perimetro: os.PathLike
) -> os.PathLike:
    """
    Extrai os vértices do perímetro como pontos, em ordem do anel.

    Substitui FeatureToLine + FeatureVerticesToPoints (licença Advanced).
    O último ponto repete o primeiro (fechamento), como no fluxo original.
    """
    desc = arcpy.Describe(feicao_perimetro)
    sr = desc.spatialReference
    out_name = 'vertices_feicao'
    out_fc = os.path.join(arcpy.env.scratchGDB, out_name)

    if arcpy.Exists(out_fc):
        arcpy.Delete_management(out_fc)

    arcpy.management.CreateFeatureclass(
        out_path=arcpy.env.scratchGDB,
        out_name=out_name,
        geometry_type='POINT',
        spatial_reference=sr
    )

    pontos = []
    with arcpy.da.SearchCursor(feicao_perimetro, ['SHAPE@']) as cursor:
        for row in cursor:
            geom = row[0]
            if geom is None:
                continue
            for part in geom:
                part_pts = [p for p in part if p is not None]
                if not part_pts:
                    continue
                # remove fechamento duplicado do anel
                if len(part_pts) > 1 and _ponto_igual(part_pts[0], part_pts[-1]):
                    part_pts = part_pts[:-1]
                pontos.extend(part_pts)
                if part_pts:
                    pontos.append(part_pts[0])

    if not pontos:
        raise ValueError('Nenhum vértice encontrado no perímetro do bairro.')

    with arcpy.da.InsertCursor(out_fc, ['SHAPE@']) as icursor:
        for ponto in pontos:
            icursor.insertRow([ponto])

    arcpy.AddMessage(f'Vertices gerados sem licença Advanced: {len(pontos)} pontos')
    return out_fc
