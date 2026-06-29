# -*- coding: utf-8 -*-

from collections import Counter, defaultdict

import arcpy


def calcular_gestao_equipe(quadras_layer, lotes_layer) -> list:
    """
    Calcula contagem de lotes e vetorização por usuário em cada quadra.

    Args:
        quadras_layer: Feature layer de quadras filtrado por n_coletivo.
        lotes_layer: Feature layer de lotes filtrado por n_coletivo.

    Returns:
        Lista de dicionários por quadra, ordenada por número da quadra.
    """
    quadras = set()
    with arcpy.da.SearchCursor(quadras_layer, ['quadra']) as cursor:
        for (quadra,) in cursor:
            quadras.add(quadra)

    por_quadra = defaultdict(lambda: {'lotes': 0, 'usuarios': Counter()})

    with arcpy.da.SearchCursor(lotes_layer, ['quadra', 'created_user']) as cursor:
        for quadra, usuario in cursor:
            quadras.add(quadra)
            usuario = (usuario or '').strip() or 'desconhecido'
            por_quadra[quadra]['lotes'] += 1
            por_quadra[quadra]['usuarios'][usuario] += 1

    resultado = []
    for numero in sorted(quadras):
        dados_quadra = por_quadra[numero]
        vetorizacao = [
            {'usuario': usuario, 'quantidade': quantidade}
            for usuario, quantidade in sorted(dados_quadra['usuarios'].items())
        ]
        resultado.append({
            'numero': numero,
            'lotes': dados_quadra['lotes'],
            'vetorizacao': vetorizacao
        })

    return resultado
