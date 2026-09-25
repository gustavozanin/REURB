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

A lógica pura (`atributos_segmento`, `azimute_graus_decimais`,
`azimute_gms`) não depende de ArcPy e é testável isoladamente (ver
`_TI_apenas/tests_memorial/test_azimute_utm.py`). `calcular_atributos_vertices`
é um wrapper fino que aplica essa lógica a uma feição de pontos via ArcPy.
"""

import math

try:
    import arcpy
except ImportError:
    arcpy = None


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


def atributos_segmento(e1, n1, e2, n2):
    """
    Calcula azimute, distância e coordenadas do vértice de origem de um
    segmento no plano UTM.

    Args:
        e1, n1: coordenadas E/N (m) do vértice de origem.
        e2, n2: coordenadas E/N (m) do vértice de destino.

    Returns:
        dict: com chaves `azimute` (str, formato GMS), `distancia_m`
        (float), `E` (float, igual a e1) e `N` (float, igual a n1).
    """
    delta_e = e2 - e1
    delta_n = n2 - n1
    distancia_m = math.hypot(delta_e, delta_n)
    az = azimute_graus_decimais(delta_e, delta_n)
    return {
        'azimute': azimute_gms(az),
        'distancia_m': distancia_m,
        'E': e1,
        'N': n1,
    }


def calcular_atributos_vertices(fc_pontos, campo_e='E', campo_n='N', campo_azimute='azimute'):
    """
    Wrapper ArcPy: preenche E, N e azimute (texto GMS) na feição de pontos
    do perímetro, assumindo que ela já está no SR UTM do fuso do processo.

    Cada vértice recebe o azimute/E/N do segmento até o PRÓXIMO vértice
    (ordem de OBJECTID), fechando o anel do último vértice para o primeiro.
    A distância por segmento fica a cargo de `transforma_vertices_em_linhas`
    (via `CalculateGeometryAttributes`), que opera sobre as linhas geradas
    a partir destes pontos.

    Args:
        fc_pontos: caminho da feição de pontos (ordem = ordem do anel).
        campo_e / campo_n / campo_azimute: nomes dos campos a preencher.

    Returns:
        None (atualização in-place da feição).

    Raises:
        RuntimeError: se ArcPy não estiver disponível no ambiente atual.
        ValueError: se a feição tiver menos de 2 vértices.
    """
    if arcpy is None:
        raise RuntimeError('arcpy não disponível neste ambiente.')

    campos_existentes = [f.name for f in arcpy.ListFields(fc_pontos)]
    campos_novos = []
    if campo_e not in campos_existentes:
        campos_novos.append([campo_e, 'DOUBLE', campo_e])
    if campo_n not in campos_existentes:
        campos_novos.append([campo_n, 'DOUBLE', campo_n])
    if campo_azimute not in campos_existentes:
        campos_novos.append([campo_azimute, 'TEXT', campo_azimute])
    if campos_novos:
        arcpy.management.AddFields(fc_pontos, campos_novos)

    with arcpy.da.SearchCursor(fc_pontos, ['OID@', 'SHAPE@X', 'SHAPE@Y']) as cursor:
        coordenadas = {oid: (x, y) for oid, x, y in cursor}

    oids_em_ordem = sorted(coordenadas.keys())
    total = len(oids_em_ordem)
    if total < 2:
        raise ValueError('Feição de pontos precisa de ao menos 2 vértices.')

    atributos_por_oid = {}
    for indice, oid in enumerate(oids_em_ordem):
        e1, n1 = coordenadas[oid]
        oid_proximo = oids_em_ordem[(indice + 1) % total]
        e2, n2 = coordenadas[oid_proximo]
        atributos_por_oid[oid] = atributos_segmento(e1, n1, e2, n2)

    with arcpy.da.UpdateCursor(fc_pontos, ['OID@', campo_e, campo_n, campo_azimute]) as cursor:
        for row in cursor:
            oid = row[0]
            atributos = atributos_por_oid[oid]
            row[1] = atributos['E']
            row[2] = atributos['N']
            row[3] = atributos['azimute']
            cursor.updateRow(row)
