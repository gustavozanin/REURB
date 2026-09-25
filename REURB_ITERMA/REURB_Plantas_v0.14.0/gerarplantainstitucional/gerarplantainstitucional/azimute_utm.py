# -*- coding: utf-8 -*-
"""Azimute, distância e coordenadas E/N no plano UTM do fuso do processo.

Diferente de `gerarplantanucleo/gerarplantanucleo/azminute.py` — que
assume as coordenadas da feição de entrada como estão, tipicamente em
graus geográficos (SIRGAS 2000 geográfico) —, este módulo é usado
depois que o perímetro já foi exportado/reprojetado para o SR UTM do
fuso do processo (ver `fusos_utm.py` / `exporta_shapefile.py`). Nesse
plano cartesiano, ΔE e ΔN em metros já são distâncias reais, então a
fórmula do azimute cartográfico (a partir do norte, sentido horário) e
a distância euclidiana entre os pontos são diretamente válidas — sem
as distorções de calcular sobre graus de latitude/longitude.

A lógica pura (`azimute_graus_decimais`, `azimute_gms`) não depende de
ArcPy e é usada por `motor_perimetro`.
"""

import math


def azimute_graus_decimais(delta_e, delta_n):
    """
    Azimute cartográfico (a partir do norte, sentido horário) em graus decimais.

    Args:
        delta_e: diferença de coordenada Este/E (m) entre destino e origem.
        delta_n: diferença de coordenada Norte/N (m) entre destino e origem.

    Returns:
        float: azimute em graus decimais, no intervalo [0, 360).
    """
    az = math.degrees(math.atan2(delta_e, delta_n))
    if az < 0:
        az += 360
    return az


def azimute_gms(az_graus_decimais):
    """
    Converte azimute em graus decimais para o formato graus/minutos/segundos.

    Args:
        az_graus_decimais: azimute em graus decimais.

    Returns:
        str: azimute formatado como `graus° minutos' segundos"`.
    """
    graus = int(az_graus_decimais)
    minutos_flutuantes = (az_graus_decimais - graus) * 60
    minutos = int(minutos_flutuantes)
    segundos = round((minutos_flutuantes - minutos) * 60, 2)
    if segundos >= 60:
        segundos = 0.0
        minutos += 1
    if minutos >= 60:
        minutos = 0
        graus = (graus + 1) % 360
    return f'{graus}\u00b0 {minutos:02d}\' {segundos:05.2f}"'
