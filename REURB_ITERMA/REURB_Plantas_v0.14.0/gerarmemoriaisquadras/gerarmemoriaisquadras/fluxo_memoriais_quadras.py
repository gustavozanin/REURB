# -*- coding: utf-8 -*-
"""Fluxo ArcGIS Pro para emitir um memorial por quadra."""
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path

import arcpy

from memorial_quadras_core import (
    auditoria,
    epsg_sirgas_2000_utm,
    pontos_controle_de_geojson,
    segmentos_de_aneis,
    slug,
)

FEATURESERVER_URL_PADRAO = (
    "https://www.arcgis.iterma.ma.gov.br/server/rest/services/"
    "CAMADAS_ITERMA/REURB_ITERMA/FeatureServer"
)

LIMITE_QUADRA_CONFRONTANTE_M = 0.5
LIMITE_POLIGONO_CONFRONTANTE_M = 5
# Recorte da layer 1 no entorno do bairro (carrega candidatos; o match usa 5 m).
DISTANCIA_CARGA_EXTERNO_M = 50.0
BUFFER_CONFRONTANTE_EXTERNO_M = 5.0
# Sobreposição de aresta: frente curta ainda vale se cobre boa parte do segmento.
OVERLAP_MINIMO_FRACAO_SEGMENTO = 0.40
# Eixo viário à frente da testada (mesma régua do memorial institucional de lote).
PARALELISMO_MINIMO_EIXO = 0.707
PARALELISMO_MINIMO_EIXO_FALLBACK = 0.5
PARALELISMO_MINIMO_EIXO_ULTIMO = 0.3
DISTANCIA_MAX_EIXO_M = 50.0
COMPRIMENTO_MAX_ABSORCAO_CONFRONTANTE_M = 15.0
# Chanfro de esquina: trecho curto onde as frentes vizinhas mudam de direção.
COMPRIMENTO_MAX_ESQUINA_M = 15.0
DEFLEXAO_MINIMA_ESQUINA_GRAUS = 20.0
_PADRAO_TRAVESSA = re.compile(r"\bTRAVESSA\b", re.IGNORECASE)
_PADRAO_LOGRADOURO = re.compile(
    r"\b(RUA|AVENIDA|AV\.?|TRAVESSA|TV\.?|RODOVIA|ESTRADA|ALAMEDA|"
    r"PRA[CÇ]A|VIELA|BECO|FAIXA)\b|^MA\s*[-–]?\s*\d+",
    re.IGNORECASE,
)
_SONDAS_NORMAL_EXTERNA = (0.5, 1, 2, 5, 10, 20, 50)


def _log(messages, texto, aviso=False):
    fn = None
    if messages:
        fn = getattr(
            messages,
            "addWarningMessage" if aviso else "addMessage",
            None,
        )
    (fn or (arcpy.AddWarning if aviso else arcpy.AddMessage))(texto)


def _campo(dataset, candidatos, obrigatorio=True):
    campos = {f.name.casefold(): f.name for f in arcpy.ListFields(dataset)}
    for nome in candidatos:
        if nome.casefold() in campos:
            return campos[nome.casefold()]
    if obrigatorio:
        nomes = ", ".join(candidatos)
        raise ValueError(
            f"Campos esperados não encontrados ({nomes}): {dataset}"
        )


def _where(dataset, campo, valor):
    delimitado = arcpy.AddFieldDelimiters(dataset, campo)
    texto = str(valor).replace(chr(39), chr(39) * 2)
    return f"{delimitado} = '{texto}'"


def _layer(nome, fonte, where=None):
    if arcpy.Exists(nome):
        arcpy.management.Delete(nome)
    arcpy.management.MakeFeatureLayer(fonte, nome, where)
    return nome


def _aneis(geom):
    saida = []
    for parte in geom:
        anel = []
        for p in parte:
            if p is None:
                if anel:
                    saida.append(anel)
                    anel = []
            else:
                anel.append((p.X, p.Y))
        if anel:
            saida.append(anel)
    return saida


def _aneis_controle(geom, sr):
    """Vértices do projeto, projetados no fuso, sem densificar o arco."""
    import json

    try:
        dados = json.loads(geom.JSON or '{}')
    except (TypeError, ValueError):
        dados = {}
    aneis = pontos_controle_de_geojson(dados)
    if not aneis:
        return _aneis(geom.projectAs(sr) if sr else geom)
    sr_orig = geom.spatialReference
    saida = []
    for anel in aneis:
        projetado = []
        for x, y in anel:
            ponto = arcpy.PointGeometry(arcpy.Point(x, y), sr_orig)
            if sr is not None:
                ponto = ponto.projectAs(sr)
            p = ponto.firstPoint
            projetado.append((p.X, p.Y))
        saida.append(projetado)
    return saida


def _sr_utm(geom):
    ponto = arcpy.PointGeometry(
        geom.centroid, geom.spatialReference
    ).projectAs(arcpy.SpatialReference(4326)).firstPoint
    return arcpy.SpatialReference(epsg_sirgas_2000_utm(ponto.X, ponto.Y))


def _status_pronto(valor):
    # O FeatureServer pode devolver o status como número (2.0) em vez de texto ("2").
    try:
        return int(float(valor)) in {2, 4}
    except (TypeError, ValueError):
        return str(valor).strip() in {"2", "4"}


def _resolver_bairro(fonte, numero):
    campo_numero = _campo(fonte, ["n_coletivo", "coletivo", "reurb"])
    lyr = _layer("memq_bairro", fonte, _where(fonte, campo_numero, numero))
    qtd = int(arcpy.management.GetCount(lyr)[0])
    if qtd != 1:
        raise ValueError(
            f"O REURB deve identificar exatamente um Bairro; encontrados: {qtd}."
        )
    nome = _campo(lyr, ["nome", "bairro"], False)
    status = _campo(lyr, ["status"], False)
    rt = _campo(lyr, ["responsavel_tecnico"], False)
    campos = ["SHAPE@"] + [x for x in [nome, status, rt] if x]
    row = next(arcpy.da.SearchCursor(lyr, campos))
    dados = dict(zip(campos, row))
    if status and not _status_pronto(dados.get(status)):
        raise ValueError(
            f"Bairro não está pronto para emissão (status {dados.get(status)})."
        )
    return lyr, dados["SHAPE@"], str(dados.get(nome) or ""), str(dados.get(rt) or "")


def _quadras(fonte, bairro_lyr, numero):
    campo_numero = _campo(fonte, ["n_coletivo", "coletivo", "reurb"], False)
    lyr = _layer(
        "memq_quadras",
        fonte,
        _where(fonte, campo_numero, numero) if campo_numero else None,
    )
    if not campo_numero or int(arcpy.management.GetCount(lyr)[0]) == 0:
        # Sem recriar o layer, o filtro por número continuaria ativo e a
        # seleção espacial também traria zero quadras.
        lyr = _layer("memq_quadras", fonte)
        arcpy.management.SelectLayerByLocation(
            lyr, "INTERSECT", bairro_lyr
        )
    return lyr, _campo(lyr, ["quadra", "numero", "nome"])


def _eixos(fonte, sr):
    nome = _campo(fonte, ["logradouro", "nome", "rua"], False)
    if not nome:
        return []
    with arcpy.da.SearchCursor(fonte, [nome, "SHAPE@"]) as cursor:
        return [
            (str(n or "").strip(), g.projectAs(sr))
            for n, g in cursor if g
        ]


def _externos(fonte, sr, referencia_lyr=None, messages=None):
    nome = _campo(fonte, ["nome", "confrontante"], False)
    if not nome:
        _log(
            messages,
            "Camada Confrontante Externo sem campo 'nome' ou 'confrontante'; "
            "a camada foi ignorada.",
            aviso=True,
        )
        return []
    lyr = _layer("memq_externos", fonte)
    if referencia_lyr:
        arcpy.management.SelectLayerByLocation(
            lyr,
            "WITHIN_A_DISTANCE",
            referencia_lyr,
            f"{DISTANCIA_CARGA_EXTERNO_M} Meters",
            "NEW_SELECTION",
        )
    pares = []
    with arcpy.da.SearchCursor(lyr, [nome, "SHAPE@"]) as cursor:
        for n, g in cursor:
            if g and str(n or "").strip():
                pares.append((str(n).strip(), g.projectAs(sr)))
    tipo = pares[0][1].type if pares else ""
    _log(
        messages,
        f"Confrontante Externo no entorno: {len(pares)} feição(ões)"
        + (f" (geometria {tipo})." if tipo else "."),
    )
    if not pares:
        _log(
            messages,
            "Nenhuma feição de Confrontante Externo no entorno do bairro. "
            "Confira a camada no mapa (layer 1).",
            aviso=True,
        )
    return pares


def _scratch(nome):
    return os.path.join(arcpy.env.scratchGDB, nome)


def _recriar_fc(caminho):
    if arcpy.Exists(caminho):
        arcpy.management.Delete(caminho)


def _aceita_overlap(overlap_m, comprimento_segmento_m, limite_overlap_m):
    """Separa frente real de simples toque de canto entre as feições."""
    if overlap_m <= 0:
        return False
    if overlap_m >= limite_overlap_m:
        return True
    if comprimento_segmento_m <= 0:
        return False
    return overlap_m >= OVERLAP_MINIMO_FRACAO_SEGMENTO * comprimento_segmento_m


def _campo_intersect(tabela, base):
    # O intersect renomeia campos repetidos entre as entradas (seg_idx -> seg_idx_1).
    campos = [f.name for f in arcpy.ListFields(tabela)]
    for nome in campos:
        if nome.casefold() == base.casefold():
            return nome
    for nome in campos:
        if nome.casefold().startswith(base.casefold()):
            return nome
    raise ValueError(f"Campo {base} não encontrado em {tabela}.")


def _criar_fc_segmentos_temp(segmentos, nome, sr):
    caminho = _scratch(nome)
    _recriar_fc(caminho)
    arcpy.management.CreateFeatureclass(
        arcpy.env.scratchGDB, nome, "POLYLINE", spatial_reference=sr
    )
    arcpy.management.AddField(caminho, "seg_idx", "LONG")
    with arcpy.da.InsertCursor(caminho, ["SHAPE@", "seg_idx"]) as cursor:
        for i, x in enumerate(segmentos):
            cursor.insertRow([_polyline_segmento(x, sr), i])
    return caminho


def _criar_fc_candidatos_temp(pares, nome, sr):
    validos = [
        (str(n or "").strip(), g)
        for n, g in pares if g and str(n or "").strip()
    ]
    if not validos:
        return None
    tipo = validos[0][1].type.upper()
    caminho = _scratch(nome)
    _recriar_fc(caminho)
    arcpy.management.CreateFeatureclass(
        arcpy.env.scratchGDB, nome, tipo, spatial_reference=sr
    )
    arcpy.management.AddField(caminho, "conf_nome", "TEXT", field_length=120)
    with arcpy.da.InsertCursor(caminho, ["SHAPE@", "conf_nome"]) as cursor:
        for n, g in validos:
            if g.type.upper() == tipo:
                cursor.insertRow([g, n])
    return caminho


def _melhor_por_aresta_temp(
    segmentos, sr, pares, prefixo, buffer_m, limite_overlap_m
):
    """Confrontante de maior sobreposição com a aresta de cada segmento.

    Buffer fino no vizinho + intersect com a linha da aresta: quem só
    encosta no vértice gera sobreposição desprezível e é descartado.
    """
    fc_candidatos = _criar_fc_candidatos_temp(pares, f"{prefixo}_cand", sr)
    if not fc_candidatos:
        return {}
    fc_segmentos = _criar_fc_segmentos_temp(segmentos, f"{prefixo}_seg", sr)
    fc_buffer = _scratch(f"{prefixo}_buf")
    _recriar_fc(fc_buffer)
    fc_intersect = _scratch(f"{prefixo}_int")
    _recriar_fc(fc_intersect)
    try:
        arcpy.analysis.PairwiseBuffer(
            fc_candidatos, fc_buffer, f"{buffer_m} Meters", dissolve_option="NONE"
        )
        # Intersect da aresta (linha) com o buffer do vizinho: SHAPE@LENGTH
        # é o comprimento da frente, não o perímetro do polígono no canto.
        arcpy.analysis.PairwiseIntersect(
            [fc_segmentos, fc_buffer], fc_intersect
        )
        campo_idx = _campo_intersect(fc_intersect, "seg_idx")
        campo_nome = _campo_intersect(fc_intersect, "conf_nome")
        overlaps = defaultdict(lambda: defaultdict(float))
        with arcpy.da.SearchCursor(
            fc_intersect, [campo_idx, campo_nome, "SHAPE@LENGTH"]
        ) as cursor:
            for idx, nome, comprimento in cursor:
                if idx is None or not str(nome or "").strip():
                    continue
                overlaps[int(idx)][str(nome).strip()] += float(comprimento or 0)
        melhor = {}
        for idx, candidatos in overlaps.items():
            nome, overlap = max(candidatos.items(), key=lambda item: item[1])
            if _aceita_overlap(
                overlap,
                float(segmentos[idx].get("distancia") or 0),
                limite_overlap_m,
            ):
                melhor[idx] = (nome, overlap)
        return melhor
    finally:
        for caminho in (fc_candidatos, fc_segmentos, fc_buffer, fc_intersect):
            _recriar_fc(caminho)


def _polyline_segmento(seg, sr):
    p1 = arcpy.Point(float(seg["eLong"]), float(seg["nLat"]))
    p2 = arcpy.Point(float(seg["este_para"]), float(seg["norte_para"]))
    return arcpy.Polyline(arcpy.Array([p1, p2]), sr)


def _cosseno_paralelismo(vetor_a, vetor_b):
    ax, ay = vetor_a
    bx, by = vetor_b
    ma = math.hypot(ax, ay)
    mb = math.hypot(bx, by)
    if not ma or not mb:
        return 0.0
    return abs(ax * bx + ay * by) / (ma * mb)


def _tangente_segmento(linha):
    antes = linha.positionAlongLine(0.45, True).firstPoint
    depois = linha.positionAlongLine(0.55, True).firstPoint
    return depois.X - antes.X, depois.Y - antes.Y


def _tangente_eixo(linha, distancia_m):
    comprimento = float(linha.length or 0)
    if comprimento <= 0:
        return 0.0, 0.0
    passo = min(0.5, max(0.1, comprimento * 0.05))
    d0 = max(0.0, distancia_m - passo)
    d1 = min(comprimento, distancia_m + passo)
    if d1 <= d0:
        d0 = max(0.0, distancia_m - 0.1)
        d1 = min(comprimento, distancia_m + 0.1)
    p0 = linha.positionAlongLine(d0, False).firstPoint
    p1 = linha.positionAlongLine(d1, False).firstPoint
    return p1.X - p0.X, p1.Y - p0.Y


def _primeira_saida_poligono(meio, nx, ny, anel, distancias=_SONDAS_NORMAL_EXTERNA):
    """Menor distância em que a sonda perpendicular deixa o polígono, ou None."""
    sr = anel.spatialReference
    for distancia in distancias:
        sonda = arcpy.PointGeometry(
            arcpy.Point(meio.X + nx * distancia, meio.Y + ny * distancia), sr
        )
        try:
            if not anel.contains(sonda):
                return float(distancia)
        except Exception:
            pass
    return None


def _normal_externa_segmento(linha, anel, centroide):
    """Vetor unitário perpendicular à aresta, apontando para fora da quadra."""
    meio = linha.positionAlongLine(0.5, True).firstPoint
    tx, ty = _tangente_segmento(linha)
    modulo = math.hypot(tx, ty)
    if not modulo:
        if centroide is None:
            return 0.0, 1.0
        dx, dy = meio.X - centroide.X, meio.Y - centroide.Y
        distancia = math.hypot(dx, dy) or 1.0
        return dx / distancia, dy / distancia
    nx, ny = -ty / modulo, tx / modulo
    if anel is not None:
        try:
            saida_pos = _primeira_saida_poligono(meio, nx, ny, anel)
            saida_neg = _primeira_saida_poligono(meio, -nx, -ny, anel)
            if saida_pos is not None and saida_neg is not None:
                return (nx, ny) if saida_pos <= saida_neg else (-nx, -ny)
            if saida_pos is not None:
                return nx, ny
            if saida_neg is not None:
                return -nx, -ny
            if centroide is not None:
                rx, ry = meio.X - centroide.X, meio.Y - centroide.Y
                # Produto vetorial tangente x centro→meio: indica o lado
                # externo em reentrâncias.
                if tx * rx - ty * ry > 0:
                    return -nx, -ny
                return nx, ny
        except Exception:
            pass
    if centroide is not None:
        for candidato in ((nx, ny), (-nx, -ny)):
            if (
                candidato[0] * (meio.X - centroide.X)
                + candidato[1] * (meio.Y - centroide.Y) > 0
            ):
                return candidato
    return nx, ny


def _avaliar_candidatos_eixo(linha, eixos, anel, centroide, par_minimo, limite_eixo):
    """Candidatos de eixo à frente da testada (lado externo + distância + paralelismo)."""
    if linha is None or linha.length == 0:
        return []
    normal = _normal_externa_segmento(linha, anel, centroide)
    meio = linha.positionAlongLine(0.5, True).firstPoint
    tangente_seg = _tangente_segmento(linha)
    aprovados = []
    for nome, eixo_shape in eixos:
        if not eixo_shape:
            continue
        proximo_geom, dist_along, dist_from, _ = eixo_shape.queryPointAndDistance(
            meio
        )
        proximo = proximo_geom.firstPoint
        vx, vy = proximo.X - meio.X, proximo.Y - meio.Y
        if vx * normal[0] + vy * normal[1] <= 0 or dist_from > limite_eixo:
            continue
        par = _cosseno_paralelismo(
            tangente_seg, _tangente_eixo(eixo_shape, dist_along)
        )
        if par < par_minimo:
            continue
        if not nome or not str(nome).strip():
            continue
        aprovados.append((par, float(dist_from), str(nome).strip()))
    return aprovados


def _escolher_melhor_eixo(aprovados):
    """Entre eixos paralelos à testada, fica o mais próximo. Retorna (nome, distância)."""
    if not aprovados:
        return None
    melhor = min(aprovados, key=lambda item: (item[1], -item[0]))
    return melhor[2], melhor[1]


def _indices_por_parte(segmentos):
    """Índices dos segmentos agrupados por anel, na ordem do memorial."""
    por_parte = defaultdict(list)
    for i, x in enumerate(segmentos):
        por_parte[x.get("parte", 1)].append(i)
    return por_parte


def _vetor_segmento(seg):
    return (
        float(seg["este_para"]) - float(seg["eLong"]),
        float(seg["norte_para"]) - float(seg["nLat"]),
    )


def _angulo_deflexao(prev, proximo):
    """Ângulo em graus entre a direção da frente anterior e da seguinte."""
    ax, ay = _vetor_segmento(prev)
    bx, by = _vetor_segmento(proximo)
    ma = math.hypot(ax, ay)
    mb = math.hypot(bx, by)
    if not ma or not mb:
        return 0.0
    cosseno = max(-1.0, min(1.0, (ax * bx + ay * by) / (ma * mb)))
    return math.degrees(math.acos(cosseno))


def _eh_segmento_esquina(seg, prev, proximo):
    """Trecho curto entre frentes que mudam de direção: chanfro de esquina."""
    try:
        dist = float(seg.get("distancia") or 0)
    except (TypeError, ValueError):
        return False
    if dist >= COMPRIMENTO_MAX_ESQUINA_M:
        return False
    return _angulo_deflexao(prev, proximo) >= DEFLEXAO_MINIMA_ESQUINA_GRAUS


def _marcar_esquinas(segmentos):
    """Grava o indicador de esquina em cada segmento (1 = chanfro de esquina)."""
    for ordem in _indices_por_parte(segmentos).values():
        n = len(ordem)
        for pos in range(n):
            i = ordem[pos]
            if n < 3:
                segmentos[i]["esquina"] = 0
                continue
            prev = segmentos[ordem[(pos - 1) % n]]
            proximo = segmentos[ordem[(pos + 1) % n]]
            segmentos[i]["esquina"] = (
                1 if _eh_segmento_esquina(segmentos[i], prev, proximo) else 0
            )


def _vertice_esquina(seg):
    """Referência da esquina: meio do chanfro, equidistante das duas frentes."""
    return arcpy.Point(
        (float(seg["eLong"]) + float(seg["este_para"])) / 2,
        (float(seg["nLat"]) + float(seg["norte_para"])) / 2,
    )


def _escolher_eixo_esquina(ponto, eixos, limite_eixo, preferidos=None):
    """Na esquina vale o eixo mais próximo do vértice; sem paralelismo e sem lado externo.

    O teste de lado externo usado nas frentes reprova as duas vias do cruzamento:
    a normal do chanfro aponta na diagonal e o ponto mais próximo de cada via fica
    de través, com projeção negativa, enquanto uma via distante do outro lado da
    quadra projeta positivo e venceria.

    Com ``preferidos`` a escolha fica restrita a esses nomes; devolve None quando
    nenhum deles alcança o vértice, para o chamador decidir o próximo passo.
    """
    candidatos = []
    for nome, eixo_shape in eixos:
        if not eixo_shape:
            continue
        if not nome or not str(nome).strip():
            continue
        rotulo = str(nome).strip()
        if preferidos is not None and rotulo not in preferidos:
            continue
        _, _, dist_from, _ = eixo_shape.queryPointAndDistance(ponto)
        if dist_from > limite_eixo:
            continue
        candidatos.append((float(dist_from), rotulo))
    if not candidatos:
        return None
    melhor = min(candidatos, key=lambda c: c[0])
    return melhor[1], melhor[0]


def _propagar_eixo_entre_vizinhos(por_eixo, ordem):
    """Herda logradouro quando vizinhos consecutivos do anel concordam (chanfros)."""
    n = len(ordem)
    if n < 3:
        return dict(por_eixo)
    resultado = dict(por_eixo)
    for _ in range(n):
        alterou = False
        for i in range(n):
            idx = ordem[i]
            if resultado.get(idx):
                continue
            prev_log = resultado.get(ordem[(i - 1) % n])
            next_log = resultado.get(ordem[(i + 1) % n])
            if prev_log and prev_log == next_log:
                resultado[idx] = prev_log
                alterou = True
        if not alterou:
            break
    return resultado


def _eh_externo(segmento):
    return (
        segmento.get("tipo_confrontante") == "externo"
        and str(segmento.get("confrontante") or "").strip()
    )


def _copiar_confrontante_externo(origem, destino):
    destino["confrontante"] = origem["confrontante"]
    destino["tipo_confrontante"] = origem.get("tipo_confrontante")
    if "distancia_confrontante_m" in origem:
        destino["distancia_confrontante_m"] = origem.get("distancia_confrontante_m")
    elif "distancia_confrontante_m" in destino:
        del destino["distancia_confrontante_m"]


def _propagar_externo_entre_vizinhos(segmentos, ordem):
    """Preenche lacunas entre dois trechos consecutivos com o mesmo confrontante externo."""
    n = len(ordem)
    if n < 3:
        return
    for _ in range(n):
        alterou = False
        for i in range(n):
            idx = ordem[i]
            if segmentos[idx].get("confrontante"):
                continue
            prev = segmentos[ordem[(i - 1) % n]]
            prox = segmentos[ordem[(i + 1) % n]]
            if not _eh_externo(prev) or not _eh_externo(prox):
                continue
            if prev["confrontante"] != prox["confrontante"]:
                continue
            _copiar_confrontante_externo(prev, segmentos[idx])
            alterou = True
        if not alterou:
            break


def _geom_externo_mais_proxima(nome, linha, externos, limite_m):
    """Geometria do externo com esse nome mais próxima do segmento.

    No FeatureServer o mesmo nome pode repetir em feições distantes; o dicionário
    simples por nome ficava só com a última e reprovava a propagação unilateral.
    """
    rotulo = str(nome or "").strip()
    if not rotulo:
        return None, None
    candidatos = [
        g for n, g in externos if g and str(n or "").strip() == rotulo
    ]
    if not candidatos:
        chave = rotulo.casefold()
        candidatos = [
            g for n, g in externos
            if g and str(n or "").strip().casefold() == chave
        ]
    if not candidatos:
        return None, None
    geom = min(candidatos, key=lambda g: float(linha.distanceTo(g)))
    dist = float(linha.distanceTo(geom))
    if dist > limite_m:
        return None, None
    return geom, dist


def _preencher_externo_por_vizinho(segmentos, ordem, externos, sr):
    """Herda externo de vizinho único quando o segmento encosta na geometria do confrontante."""
    n = len(ordem)
    for i in range(n):
        idx = ordem[i]
        if segmentos[idx].get("confrontante"):
            continue
        prev = segmentos[ordem[(i - 1) % n]]
        prox = segmentos[ordem[(i + 1) % n]]
        prev_ext = _eh_externo(prev)
        prox_ext = _eh_externo(prox)
        if prev_ext and prox_ext:
            continue
        if not prev_ext and not prox_ext:
            continue
        viz = prox if prox_ext else prev
        linha = _polyline_segmento(segmentos[idx], sr)
        if _geom_externo_mais_proxima(
            viz["confrontante"], linha, externos, BUFFER_CONFRONTANTE_EXTERNO_M
        )[1] is None:
            continue
        _copiar_confrontante_externo(viz, segmentos[idx])


def _preencher_externo_por_proximidade(segmentos, externos, sr, limite_m):
    """Usa o confrontante externo nomeado mais próximo se o trecho ainda está vazio."""
    if not externos:
        return
    for seg in segmentos:
        if str(seg.get("confrontante") or "").strip():
            continue
        linha = _polyline_segmento(seg, sr)
        melhor = None
        for nome, geom in externos:
            if not geom or not str(nome or "").strip():
                continue
            dist = float(linha.distanceTo(geom))
            if dist > limite_m:
                continue
            if melhor is None or dist < melhor[0]:
                melhor = (dist, str(nome).strip())
        if melhor:
            seg.update(
                confrontante=melhor[1],
                tipo_confrontante="externo",
                distancia_confrontante_m=round(melhor[0], 2),
            )


def _eh_travessa_isolada(nome):
    return bool(_PADRAO_TRAVESSA.search(nome or ""))


def _eh_logradouro(nome):
    texto = (nome or "").strip()
    if not texto:
        return False
    if _eh_travessa_isolada(texto):
        return True
    return bool(_PADRAO_LOGRADOURO.search(texto))


def _absorver_confrontantes_curtos(
    segmentos, ordem, limite_m=COMPRIMENTO_MAX_ABSORCAO_CONFRONTANTE_M
):
    """Absorve trechos curtos entre vizinhos iguais (cruzamento falso de eixo)."""
    n = len(ordem)
    if n < 3:
        return
    originais = [
        str(segmentos[i].get("confrontante") or "").strip() for i in ordem
    ]
    for pos in range(n):
        i = ordem[pos]
        atual = segmentos[i]
        try:
            dist = float(atual.get("distancia") or 0)
        except (TypeError, ValueError):
            continue
        if dist >= limite_m:
            continue
        curr = originais[pos]
        prev = originais[(pos - 1) % n]
        nxt = originais[(pos + 1) % n]
        if not curr or not prev or prev != nxt or prev == curr:
            continue
        if _eh_travessa_isolada(curr):
            continue
        if _eh_logradouro(curr) and not _eh_logradouro(prev):
            continue
        vizinho = segmentos[ordem[(pos - 1) % n]]
        atual["confrontante"] = prev
        atual["tipo_confrontante"] = vizinho.get("tipo_confrontante")
        if "distancia_confrontante_m" in vizinho:
            atual["distancia_confrontante_m"] = vizinho.get(
                "distancia_confrontante_m"
            )
        elif "distancia_confrontante_m" in atual:
            del atual["distancia_confrontante_m"]


def _aplicar_eixo_pendentes(segmentos, sr, anel, pendentes, eixos, limite_eixo):
    """Resolve o logradouro: paralelismo nas frentes e eixo mais próximo nas esquinas."""
    if not pendentes:
        return
    centroide = anel.centroid if anel is not None else None
    tiers = (
        PARALELISMO_MINIMO_EIXO,
        PARALELISMO_MINIMO_EIXO_FALLBACK,
        PARALELISMO_MINIMO_EIXO_ULTIMO,
    )
    faltam = set(pendentes)
    melhor = {}
    for i in pendentes:
        if segmentos[i].get("esquina"):
            continue
        linha = _polyline_segmento(segmentos[i], sr)
        for par_min in tiers:
            hit = _escolher_melhor_eixo(
                _avaliar_candidatos_eixo(
                    linha, eixos, anel, centroide, par_min, limite_eixo
                )
            )
            if hit:
                melhor[i] = hit
                break
    for ordem in _indices_por_parte(segmentos).values():
        n = len(ordem)
        nomes = _propagar_eixo_entre_vizinhos(
            {i: melhor[i][0] for i in ordem if i in melhor}, ordem
        )
        # Chanfro de esquina: fica entre as duas vias do cruzamento, então
        # prioriza as vias das frentes vizinhas e só depois aceita o eixo
        # mais próximo.
        for pos in range(n):
            i = ordem[pos]
            if i not in faltam or i in nomes or not segmentos[i].get("esquina"):
                continue
            vizinhos = {
                nomes[j]
                for j in (ordem[(pos - 1) % n], ordem[(pos + 1) % n])
                if nomes.get(j)
            }
            ponto = _vertice_esquina(segmentos[i])
            hit = (
                _escolher_eixo_esquina(ponto, eixos, limite_eixo, vizinhos)
                if vizinhos
                else None
            ) or _escolher_eixo_esquina(ponto, eixos, limite_eixo)
            if hit:
                melhor[i] = hit
                nomes[i] = hit[0]
        nomes = _propagar_eixo_entre_vizinhos(nomes, ordem)
        for i, nome in nomes.items():
            if i not in faltam:
                continue
            if i in melhor:
                dist = melhor[i][1]
                segmentos[i].update(
                    confrontante=nome,
                    tipo_confrontante="logradouro",
                    distancia_confrontante_m=round(dist, 2),
                )
            else:
                segmentos[i].update(
                    confrontante=nome, tipo_confrontante="logradouro"
                )


def _confrontantes(
    segmentos,
    sr,
    poligono_quadra,
    quadra_atual,
    quadras,
    externos,
    eixos,
    buffer_aresta_m,
    overlap_minimo_m,
    limite_eixo,
):
    vizinhos = [
        (n, g) for n, g in quadras if n.casefold() != quadra_atual.casefold()
    ]
    _marcar_esquinas(segmentos)
    for i, (nome, overlap) in _melhor_por_aresta_temp(
        segmentos,
        sr,
        vizinhos,
        "memq_conf_quadra",
        buffer_aresta_m,
        overlap_minimo_m,
    ).items():
        segmentos[i].update(
            confrontante=nome,
            tipo_confrontante="quadra",
            distancia_confrontante_m=round(overlap, 2),
        )
    for i, (nome, overlap) in _melhor_por_aresta_temp(
        segmentos,
        sr,
        externos,
        "memq_conf_externo",
        BUFFER_CONFRONTANTE_EXTERNO_M,
        LIMITE_QUADRA_CONFRONTANTE_M,
    ).items():
        if segmentos[i].get("confrontante"):
            continue
        segmentos[i].update(
            confrontante=nome,
            tipo_confrontante="externo",
            distancia_confrontante_m=round(overlap, 2),
        )
    for ordem in _indices_por_parte(segmentos).values():
        _propagar_externo_entre_vizinhos(segmentos, ordem)
    pendentes = [
        i for i, x in enumerate(segmentos) if not x.get("confrontante")
    ]
    _aplicar_eixo_pendentes(
        segmentos, sr, poligono_quadra, pendentes, eixos, limite_eixo
    )
    for ordem in _indices_por_parte(segmentos).values():
        _preencher_externo_por_vizinho(segmentos, ordem, externos, sr)
    _preencher_externo_por_proximidade(
        segmentos, externos, sr, BUFFER_CONFRONTANTE_EXTERNO_M
    )
    pendentes = [
        i for i, x in enumerate(segmentos) if not x.get("confrontante")
    ]
    for i in pendentes:
        if segmentos[i].get("confrontante"):
            continue
        segmentos[i].update(
            confrontante="área adjacente não identificada",
            tipo_confrontante="nao_identificado",
        )
    for ordem in _indices_por_parte(segmentos).values():
        _absorver_confrontantes_curtos(segmentos, ordem)
    return sum(
        1 for x in segmentos if x.get("tipo_confrontante") == "nao_identificado"
    )


def executar(
    numero_reurb,
    pasta_saida,
    quadras_filtro="",
    nome_rt="",
    formacao_rt="",
    crea_rt="",
    featureserver_url=FEATURESERVER_URL_PADRAO,
    distancia_logradouro_m=DISTANCIA_MAX_EIXO_M,
    gerar_consolidado=True,
    messages=None,
):
    from documentos_quadras_pdf import gerar_pdf, mesclar_pdfs

    if not numero_reurb or not pasta_saida:
        raise ValueError("Informe o número do REURB e a pasta de saída.")
    base = featureserver_url.rstrip("/")
    bairro_lyr, geom_bairro, bairro, rt_bairro = _resolver_bairro(
        f"{base}/8", numero_reurb
    )
    quadras_lyr, campo_quadra = _quadras(
        f"{base}/10", bairro_lyr, numero_reurb
    )
    sr = _sr_utm(geom_bairro)
    eixos = _eixos(f"{base}/0", sr)
    externos = _externos(f"{base}/1", sr, bairro_lyr, messages)
    desejadas = {
        x.strip().casefold()
        for x in str(quadras_filtro or "").replace(";", ",").split(",")
        if x.strip()
    }
    pasta = Path(pasta_saida) / f"memoriais_quadras_{slug(numero_reurb)}"
    pdf_dir = pasta / "memoriais_individuais"
    json_dir = pasta / "dados_json"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    with arcpy.da.SearchCursor(
        quadras_lyr, [campo_quadra, "SHAPE@"]
    ) as cursor:
        linhas = sorted(
            (
                (str(q or "Sem quadra").strip(), g)
                for q, g in cursor if g
            ),
            key=lambda x: x[0].casefold(),
        )
    quadras_utm = [(n, g.projectAs(sr)) for n, g in linhas]
    resultados = []
    pdfs = []
    rotulos = {}
    for quadra, geom in linhas:
        if desejadas and quadra.casefold() not in desejadas:
            continue
        utm = geom.projectAs(sr)
        # Quadras sem número (ou com nomes iguais depois do slug) gerariam
        # o mesmo arquivo e se apagariam.
        rotulo = slug(quadra).upper()
        rotulos[rotulo] = rotulos.get(rotulo, 0) + 1
        if rotulos[rotulo] > 1:
            rotulo = f"{rotulo}_{rotulos[rotulo]:02d}"
        total = len(linhas) if not desejadas else len(desejadas)
        _log(
            messages,
            f"Processando quadra {quadra} ({len(resultados) + 1}/{total})...",
        )
        segmentos = segmentos_de_aneis(_aneis_controle(geom, sr), prefixo=f"Q{rotulo}-P")
        faltantes = _confrontantes(
            segmentos,
            sr,
            utm,
            quadra,
            quadras_utm,
            externos,
            eixos,
            LIMITE_QUADRA_CONFRONTANTE_M,
            LIMITE_POLIGONO_CONFRONTANTE_M,
            float(distancia_logradouro_m),
        )
        qa = auditoria(segmentos, utm.length)
        meta = {
            "quadra": quadra,
            "bairro": bairro,
            "numero_reurb": numero_reurb,
            "area_m2": utm.area,
            "perimetro_m": utm.length,
            "sistema_referencia": sr.name,
            "wkid": sr.factoryCode,
            "rt_nome": nome_rt or rt_bairro,
            "rt_formacao": formacao_rt,
            "rt_crea": crea_rt,
        }
        dados = {
            "meta": meta,
            "segmentos": segmentos,
            "auditoria": qa,
            "segmentosSemConfrontante": faltantes,
        }
        nome = f"MEMORIAL_QUADRA_{rotulo}"
        jp = json_dir / f"{nome}.json"
        pp = pdf_dir / f"{nome}.pdf"
        jp.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        gerar_pdf(segmentos, meta, pp)
        pdfs.append(str(pp))
        resultados.append({
            "quadra": quadra,
            "pdf": str(pp),
            "json": str(jp),
            "auditoria": qa,
            "segmentosSemConfrontante": faltantes,
        })
    if not resultados:
        raise ValueError("Nenhuma quadra corresponde aos filtros informados.")
    consolidado = pasta / "MEMORIAIS_QUADRAS_COMPLETO.pdf"
    pdf_final = mesclar_pdfs(pdfs, consolidado) if gerar_consolidado else None
    resumo = {
        "pronto": True,
        "numeroReurb": numero_reurb,
        "bairro": bairro,
        "quantidadeQuadras": len(resultados),
        "pastaSaida": str(pasta),
        "pdfConsolidado": str(pdf_final) if pdf_final else None,
        "resultados": resultados,
    }
    (pasta / "validacao_memoriais_quadras.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return json.dumps(resumo, ensure_ascii=False)
