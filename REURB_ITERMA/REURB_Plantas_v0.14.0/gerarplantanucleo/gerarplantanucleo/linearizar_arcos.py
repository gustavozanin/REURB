# -*- coding: utf-8 -*-
"""Vértices do perímetro: os do projeto, sem inserir pontos na curva.

Memorial, quadro, planta e shapefile precisam da mesma sequência P-n que o
analista vê ao editar a feição no ArcGIS Pro. Densificar o arco (0,05 m)
criava vértices que não existem no projeto e quebrava essa conferência.

A área e o perímetro do carimbo continuam saindo da geometria original
(incluindo o arco). O memorial descreve as retas entre os vértices de
controle — os mesmos pontos do projeto.
"""

import json

import arcpy

# Mantido para conferência pontual / rotinas antigas. O fluxo de emissão
# não insere mais esses pontos na curva.
DESVIO_MAX_LINEARIZACAO_ARCOS_M = 0.05


def _par_xy(valor):
    if not isinstance(valor, (list, tuple)) or len(valor) < 2:
        return None
    if isinstance(valor[0], (int, float)) and isinstance(valor[1], (int, float)):
        return float(valor[0]), float(valor[1])
    return None


def _fim_curva(obj):
    """Ponto final de um arco/bézier no JSON Esri (chaves a, b ou c)."""
    if not isinstance(obj, dict):
        return None
    for chave in ('a', 'b', 'c'):
        trecho = obj.get(chave)
        if trecho:
            return _par_xy(trecho[0])
    return None


def pontos_controle_de_geojson(dados):
    """Anéis com os vértices de edição do projeto (sem densificar).

    Prefere curveRings (arco verdadeiro) e cai para rings. Cada arco
    contribui só com o ponto final — o mesmo que o Pro mostra.
    """
    dados = dados or {}
    aneis = []
    for chave in ('curveRings', 'rings'):
        brutos = dados.get(chave) or []
        for anel in brutos:
            pts = []
            for item in anel:
                if isinstance(item, dict):
                    fim = _fim_curva(item)
                    if fim:
                        pts.append(fim)
                else:
                    xy = _par_xy(item)
                    if xy:
                        pts.append(xy)
            if pts:
                aneis.append(pts)
        if aneis:
            break
    return aneis


def tem_curvas(geometria):
    """Geometria guardada com arcos verdadeiros em vez de segmentos retos."""
    return '"curveRings"' in (geometria.JSON or '')


def pontos_controle_de_geometria(geometria):
    """Lista de anéis [(x, y), ...] nos vértices do projeto."""
    if geometria is None:
        return []
    try:
        dados = json.loads(geometria.JSON or '{}')
    except (TypeError, ValueError):
        dados = {}
    aneis = pontos_controle_de_geojson(dados)
    if aneis:
        return aneis
    saida = []
    for parte in geometria:
        anel = []
        for ponto in parte:
            if ponto is None:
                if anel:
                    saida.append(anel)
                    anel = []
            else:
                anel.append((float(ponto.X), float(ponto.Y)))
        if anel:
            saida.append(anel)
    return saida


def linearizar_geometria(
    geometria, desvio_max_m=DESVIO_MAX_LINEARIZACAO_ARCOS_M
):
    """Devolve a geometria sem arcos e quantos vértices entraram nela.

    A densificação por DISTANCE usa uma distância maior que o próprio
    perímetro, então nenhum trecho reto é partido — só as curvas recebem
    vértices novos, a até `desvio_max_m` da curva original.

    Returns:
        tuple: `(geometria, vertices_inseridos)`; a própria geometria e 0
        quando não há arcos.
    """
    if not tem_curvas(geometria):
        return geometria, 0
    distancia_sem_efeito = max(float(geometria.length), 1.0) * 10
    linearizada = geometria.densify(
        'DISTANCE', distancia_sem_efeito, desvio_max_m
    )
    return linearizada, int(linearizada.pointCount) - int(geometria.pointCount)


def linearizar_feicao(feicao, desvio_max_m=DESVIO_MAX_LINEARIZACAO_ARCOS_M):
    """Reescreve a feição sem arcos.

    Args:
        feicao: feature class editável (não shapefile de leitura) com o
            perímetro já projetado no fuso do processo.
        desvio_max_m: desvio máximo aceito em relação à curva original.

    Returns:
        int: quantos vértices foram inseridos; 0 quando não havia arcos.
    """
    inseridos = 0
    with arcpy.da.UpdateCursor(feicao, ['SHAPE@']) as cursor:
        for row in cursor:
            geometria = row[0]
            if geometria is None:
                continue
            linearizada, novos = linearizar_geometria(geometria, desvio_max_m)
            if not novos:
                continue
            row[0] = linearizada
            cursor.updateRow(row)
            inseridos += novos
    if inseridos:
        arcpy.AddMessage(
            f'Perímetro com arcos: {inseridos} vértice(s) inserido(s) para '
            'descrever as curvas em retas, com desvio máximo de '
            f'{desvio_max_m:.2f} m.'
        )
    return inseridos
