# -*- coding: utf-8 -*-
"""Simplificação de vértices por remoção de pontos colineares.

Usado no modo de densidade `simplificado` (ver `fluxo_geracao.py`).
Remove vértices cujo desvio em relação à corda formada pelos vizinhos
mantidos seja menor ou igual à tolerância informada, em metros, no
plano cartesiano das coordenadas de entrada (assume-se SR projetado,
ex.: UTM do fuso do processo — coordenadas geográficas em graus não
produzem tolerância em metros coerente).

Lógica pura, sem dependência de ArcPy, para permitir teste unitário
isolado (ver `_TI_apenas/tests_memorial/test_simplificar_vertices.py`).
"""

import math


def _para_xy(ponto):
    """Aceita tupla/lista (x, y) ou objeto com atributos .X/.Y (ex.: arcpy.Point)."""
    if hasattr(ponto, 'X') and hasattr(ponto, 'Y'):
        return (float(ponto.X), float(ponto.Y))
    x, y = ponto
    return (float(x), float(y))


def _pontos_iguais(p1, p2, tol=1e-9):
    return abs(p1[0] - p2[0]) <= tol and abs(p1[1] - p2[1]) <= tol


def _distancia_ponto_reta(ponto, a, b):
    """Distância perpendicular de `ponto` à reta que passa por `a` e `b`.

    Se `a` e `b` coincidirem, não há reta definida; retorna a distância
    euclidiana até `a`.
    """
    px, py = ponto
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    comprimento = math.hypot(dx, dy)
    if comprimento == 0:
        return math.hypot(px - ax, py - ay)
    return abs(dy * px - dx * py + bx * ay - by * ax) / comprimento


def simplificar_anel(pontos, tolerancia_m=0.5):
    """
    Remove vértices colineares de um anel de perímetro, preservando sempre
    o primeiro e o último ponto da lista de entrada (fechamento).

    Args:
        pontos: lista ordenada de pontos do anel. Cada ponto pode ser uma
            tupla/lista (x, y) ou um objeto com atributos .X/.Y (ex.:
            arcpy.Point). Se o primeiro e o último ponto forem iguais,
            a lista é tratada como anel fechado (convenção usada por
            `transforma_feicao.py`); caso contrário, como polilinha aberta
            (ambos os extremos preservados, sem "dar a volta").
        tolerancia_m: desvio máximo, em metros, do vértice em relação à
            corda formada pelos vizinhos mantidos; vértices dentro dessa
            tolerância são removidos.

    Returns:
        list[tuple[float, float]]: pontos (x, y) simplificados. Se a
        entrada era um anel fechado, o retorno também fecha (primeiro
        ponto repetido ao final).

    Raises:
        ValueError: entrada com menos de 3 vértices distintos, ou se a
        simplificação reduzir o anel a menos de 3 vértices distintos
        (nesse caso, aumente a tolerância ou use densidade `integral`).
    """
    if not pontos:
        raise ValueError('Lista de pontos vazia.')

    coords = [_para_xy(p) for p in pontos]
    fechado = len(coords) > 1 and _pontos_iguais(coords[0], coords[-1])
    nucleo = coords[:-1] if fechado else list(coords)

    if len(nucleo) < 3:
        raise ValueError(
            'Anel de entrada precisa de ao menos 3 vértices distintos '
            f'(recebidos: {len(nucleo)}).'
        )

    mantidos = list(nucleo)
    mudou = True
    while mudou:
        mudou = False
        i = 1
        limite_superior = len(mantidos) if fechado else len(mantidos) - 1
        while i < limite_superior:
            if len(mantidos) <= 2:
                break
            anterior = mantidos[i - 1]
            if fechado:
                proximo = mantidos[(i + 1) % len(mantidos)]
            else:
                proximo = mantidos[i + 1]
            desvio = _distancia_ponto_reta(mantidos[i], anterior, proximo)
            if desvio <= tolerancia_m:
                del mantidos[i]
                mudou = True
                limite_superior = len(mantidos) if fechado else len(mantidos) - 1
            else:
                i += 1

    if len(mantidos) < 3:
        raise ValueError(
            f'Simplificação com tolerância de {tolerancia_m} m deixaria '
            f'menos de 3 vértices distintos (restariam {len(mantidos)}); '
            'aumente a tolerância ou use densidade integral.'
        )

    resultado = list(mantidos)
    if fechado:
        resultado.append(resultado[0])
    return resultado
