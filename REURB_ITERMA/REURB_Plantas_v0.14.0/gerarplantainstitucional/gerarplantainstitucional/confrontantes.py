#-*- coding: utf-8 -*-

"""Identifica confrontantes sem ferramentas de licença Advanced."""

import math
import os
import re

try:
    import arcpy
except ImportError:
    arcpy = None

from constantes import (
    BUFFER_ARESTA_CONFRONTANTE_M,
    BUFFER_BUSCA_EIXO_M,
    BUFFER_CONFRONTANTE_EXTERNO_M,
    COMPRIMENTO_MAX_ABSORCAO_CONFRONTANTE_M,
    COMPRIMENTO_MAX_QUEBRA_ABRUPTA_M,
    CONFRONTANTE_PADRAO,
    COSSENO_MAX_QUEBRA_ABRUPTA,
    DISTANCIA_MAX_EIXO_M,
    DISTANCIA_MAX_EIXO_QUEBRA_M,
    OVERLAP_MINIMO_CONFRONTANTE_M,
    OVERLAP_MINIMO_FRACAO_SEGMENTO,
    PARALELISMO_MINIMO_EIXO,
    PARALELISMO_MINIMO_EIXO_FALLBACK,
    PARALELISMO_MINIMO_EIXO_ULTIMO,
)

# Travessa isolada real: não absorver mesmo se curta e entre vizinhos iguais.
_PADRAO_TRAVESSA = re.compile(r'\bTRAVESSA\b', re.IGNORECASE)
_PADRAO_LOGRADOURO = re.compile(
    r'\b(RUA|AVENIDA|AV\.?|TRAVESSA|TV\.?|RODOVIA|ESTRADA|ALAMEDA|'
    r'PRA[CÇ]A|VIELA|BECO|FAIXA)\b|^MA\s*[-–]?\s*\d+',
    re.IGNORECASE,
)


def _eh_travessa_isolada(nome: str) -> bool:
    return bool(_PADRAO_TRAVESSA.search(nome or ''))


def _eh_logradouro(nome: str) -> bool:
    """True se o texto parece via pública (não lote/matrícula)."""
    texto = (nome or '').strip()
    if not texto:
        return False
    if _eh_travessa_isolada(texto):
        return True
    return bool(_PADRAO_LOGRADOURO.search(texto))


def absorver_confrontantes_curtos(segmentos, limite_m=None):
    """Absorve trechos curtos entre vizinhos iguais (cruzamento de eixo).

    Se o comprimento for menor que ``limite_m`` e os vizinhos imediatos
    tiverem o mesmo confrontante (diferente do atual), o trecho curto
    assume o confrontante vizinho. Travessas reais (nome com TRAVESSA)
    são preservadas. Segmentos cujo nome aparece uma única vez no anel
    e não é travessa ainda assim são absorvidos quando encaixados entre
    a mesma frente contínua (falso positivo típico de rua transversal).

    Args:
        segmentos: lista de dicts com chaves ``confrontante`` e
            ``distancia`` (metros), na ordem do anel.
        limite_m: limiar em metros (padrão da constante do módulo).

    Returns:
        tuple[list[dict], list[dict]]: (segmentos atualizados, log de
        absorções com de/para/antes/depois/distancia quando houver ``de``).
    """
    if limite_m is None:
        limite_m = COMPRIMENTO_MAX_ABSORCAO_CONFRONTANTE_M
    if len(segmentos) < 3:
        return [dict(s) for s in segmentos], []

    atualizados = [dict(s) for s in segmentos]
    originais = [
        str(s.get('confrontante') or '').strip() for s in atualizados
    ]
    n = len(atualizados)
    log = []

    for i in range(n):
        atual = atualizados[i]
        try:
            dist = float(atual.get('distancia') or 0)
        except (TypeError, ValueError):
            continue
        if dist >= limite_m:
            continue

        curr = originais[i]
        prev = originais[(i - 1) % n]
        nxt = originais[(i + 1) % n]
        if not curr or not prev or prev != nxt or prev == curr:
            continue
        if _eh_travessa_isolada(curr):
            continue
        # Não troca testada (Rua/Av.) por lote que só encosta no canto.
        if _eh_logradouro(curr) and not _eh_logradouro(prev):
            continue

        log.append(
            {
                'de': atual.get('de'),
                'antes': curr,
                'depois': prev,
                'distancia': dist,
            }
        )
        atualizados[i]['confrontante'] = prev

    return atualizados, log


def _aplicar_absorcao_confrontantes_curtos(feicao_entrada) -> int:
    """Aplica ``absorver_confrontantes_curtos`` na feição de segmentos."""
    if arcpy is None:
        raise RuntimeError('arcpy necessário para absorver confrontantes.')
    campos = [f.name for f in arcpy.ListFields(feicao_entrada)]
    if 'confrontantes' not in campos or 'distancia' not in campos:
        arcpy.AddWarning(
            'Absorção de confrontantes curtos ignorada: faltam campos '
            'confrontantes/distancia.'
        )
        return 0

    tem_de = 'de' in campos
    leitura = ['OID@', 'confrontantes', 'distancia']
    if tem_de:
        leitura.append('de')

    brutos = []
    with arcpy.da.SearchCursor(feicao_entrada, leitura) as cursor:
        for row in cursor:
            item = {
                'oid': row[0],
                'confrontante': row[1],
                'distancia': row[2],
            }
            if tem_de:
                item['de'] = row[3]
            brutos.append(item)

    # Ordena pelo número do vértice de origem quando disponível.
    if tem_de:
        def _ordem(item):
            try:
                return int(str(item.get('de') or '').split('-')[-1])
            except (TypeError, ValueError):
                return item['oid']

        brutos.sort(key=_ordem)
    else:
        brutos.sort(key=lambda item: item['oid'])

    atualizados, log = absorver_confrontantes_curtos(brutos)
    if not log:
        arcpy.AddMessage(
            'Absorção de confrontantes curtos: nenhum segmento ajustado.'
        )
        return 0

    por_oid = {item['oid']: item['confrontante'] for item in atualizados}
    with arcpy.da.UpdateCursor(feicao_entrada, ['OID@', 'confrontantes']) as cur:
        for row in cur:
            novo = por_oid.get(row[0])
            if novo is not None and row[1] != novo:
                row[1] = novo
                cur.updateRow(row)

    for item in log:
        origem = item.get('de') or '?'
        arcpy.AddMessage(
            f'Confrontante absorvido em {origem}: '
            f'"{item["antes"]}" -> "{item["depois"]}" '
            f'({item["distancia"]:.2f} m).'
        )
    arcpy.AddMessage(
        f'Absorção de confrontantes curtos: {len(log)} segmento(s) ajustado(s).'
    )
    return len(log)


def _scratch(nome: str) -> str:
    return os.path.join(arcpy.env.scratchGDB, nome)


def _recriar_fc(caminho: str) -> None:
    if arcpy.Exists(caminho):
        arcpy.Delete_management(caminho)


def _materializar(camada, nome_saida: str, where_clause: str = None) -> str:
    """Copia FeatureServer/SDE para o scratch (intersect local é mais confiável)."""
    saida = _scratch(nome_saida)
    _recriar_fc(saida)
    if where_clause:
        arcpy.analysis.Select(camada, saida, where_clause)
    else:
        arcpy.management.CopyFeatures(camada, saida)
    return saida


def _materializar_projetado(
    camada,
    nome_saida: str,
    sr_destino,
    where_clause: str = None,
) -> str:
    """Materializa camada remota e reprojeta para o SR do lote quando necessário."""
    bruto = _materializar(camada, f'{nome_saida}_bruto', where_clause)
    sr_orig = arcpy.Describe(bruto).spatialReference
    wkid_orig = getattr(sr_orig, 'factoryCode', None)
    wkid_dest = getattr(sr_destino, 'factoryCode', None)
    saida = _scratch(nome_saida)
    _recriar_fc(saida)
    if wkid_orig != wkid_dest:
        arcpy.management.Project(bruto, saida, sr_destino)
        arcpy.AddMessage(
            f'{nome_saida}: reprojetado {sr_orig.name} ({wkid_orig}) → '
            f'{sr_destino.name} ({wkid_dest})'
        )
    else:
        arcpy.management.CopyFeatures(bruto, saida)
        arcpy.AddMessage(
            f'{nome_saida}: SR já alinhado ({sr_destino.name}, WKID {wkid_dest}).'
        )
    return saida


def _recortar_ao_lote(fc, feicao_entrada, margem_m=None, prefixo='lote') -> str:
    """Limita feições à área do lote + margem (desempenho e recorte espacial)."""
    if margem_m is None:
        margem_m = BUFFER_BUSCA_EIXO_M
    linhas = _criar_midpoints(feicao_entrada, f'{prefixo}_env_seg')
    buffer_fc = arcpy.analysis.PairwiseBuffer(
        in_features=linhas,
        out_feature_class=_scratch(f'{prefixo}_env_buf'),
        buffer_distance_or_field=f'{margem_m} Meters',
        dissolve_option='ALL',
        method='PLANAR',
    )
    recortado = _scratch(f'{prefixo}_recortado')
    _recriar_fc(recortado)
    arcpy.analysis.PairwiseClip(
        in_features=fc,
        clip_features=buffer_fc,
        out_feature_class=recortado,
    )
    n = int(arcpy.management.GetCount(recortado)[0])
    arcpy.AddMessage(
        f'{prefixo} recortado ao lote (+{margem_m} m): {n} feição(ões).'
    )
    return recortado


def _recortar_eixo_ao_lote(eixo_fc, feicao_entrada, margem_m=None) -> str:
    """Limita eixos à área do lote + margem (desempenho e ruído)."""
    return _recortar_ao_lote(
        eixo_fc, feicao_entrada, margem_m=margem_m, prefixo='eixo'
    )


def _materializar_entorno(
    camada,
    nome_saida: str,
    sr_destino,
    feicao_entrada,
    margem_m=None,
) -> str:
    """Copia só as feições do FeatureServer no entorno do lote."""
    if margem_m is None:
        margem_m = BUFFER_BUSCA_EIXO_M
    linhas = _criar_midpoints(feicao_entrada, f'{nome_saida}_env_seg')
    buffer_fc = arcpy.analysis.PairwiseBuffer(
        in_features=linhas,
        out_feature_class=_scratch(f'{nome_saida}_env_buf'),
        buffer_distance_or_field=f'{margem_m} Meters',
        dissolve_option='ALL',
        method='PLANAR',
    )
    lyr = f'{nome_saida}_lyr'
    if arcpy.Exists(lyr):
        arcpy.management.Delete(lyr)
    arcpy.management.MakeFeatureLayer(camada, lyr)
    arcpy.management.SelectLayerByLocation(
        lyr, 'INTERSECT', buffer_fc, selection_type='NEW_SELECTION'
    )
    n = int(arcpy.management.GetCount(lyr)[0])
    arcpy.AddMessage(
        f'{nome_saida}: {n} feição(ões) no entorno do lote ({margem_m} m).'
    )
    if n == 0:
        arcpy.AddWarning(
            'Nenhuma feição de Confrontante Externo no entorno do lote. '
            'Confira a layer 1 no mapa.'
        )
    bruto = _scratch(f'{nome_saida}_bruto')
    _recriar_fc(bruto)
    arcpy.management.CopyFeatures(lyr, bruto)
    sr_orig = arcpy.Describe(bruto).spatialReference
    wkid_orig = getattr(sr_orig, 'factoryCode', None)
    wkid_dest = getattr(sr_destino, 'factoryCode', None)
    saida = _scratch(nome_saida)
    _recriar_fc(saida)
    if wkid_orig != wkid_dest:
        arcpy.management.Project(bruto, saida, sr_destino)
    else:
        arcpy.management.CopyFeatures(bruto, saida)
    return saida


def _criar_midpoints(feicao_entrada: os.PathLike, out_name: str = 'mid_point') -> str:
    """Copia cada segmento inteiro e preserva o vínculo com a origem."""
    desc = arcpy.Describe(feicao_entrada)
    sr = desc.spatialReference
    out_fc = _scratch(out_name)
    _recriar_fc(out_fc)

    arcpy.management.CreateFeatureclass(
        out_path=arcpy.env.scratchGDB,
        out_name=out_name,
        geometry_type='POLYLINE',
        spatial_reference=sr
    )
    arcpy.management.AddField(out_fc, 'ORIG_FID', 'LONG')
    arcpy.management.AddField(out_fc, 'SEG_OID', 'LONG')

    with arcpy.da.SearchCursor(feicao_entrada, ['OID@', 'SHAPE@']) as scur:
        with arcpy.da.InsertCursor(
            out_fc, ['SHAPE@', 'ORIG_FID', 'SEG_OID']
        ) as icur:
            for oid, shape in scur:
                if shape is None or shape.length == 0:
                    continue
                icur.insertRow([shape, oid, oid])

    return out_fc


def _criar_pontos_medios(feicao_entrada: os.PathLike, out_name: str) -> str:
    """Ponto no meio de cada segmento (ORIG_FID = OID da aresta)."""
    desc = arcpy.Describe(feicao_entrada)
    sr = desc.spatialReference
    out_fc = _scratch(out_name)
    _recriar_fc(out_fc)
    arcpy.management.CreateFeatureclass(
        out_path=arcpy.env.scratchGDB,
        out_name=out_name,
        geometry_type='POINT',
        spatial_reference=sr,
    )
    arcpy.management.AddField(out_fc, 'ORIG_FID', 'LONG')
    with arcpy.da.SearchCursor(feicao_entrada, ['OID@', 'SHAPE@']) as scur:
        with arcpy.da.InsertCursor(out_fc, ['SHAPE@', 'ORIG_FID']) as icur:
            for oid, shape in scur:
                if shape is None or shape.length == 0:
                    continue
                meio = shape.positionAlongLine(0.5, True)
                icur.insertRow([meio, oid])
    return out_fc


def _campo_join_origem(tabela) -> str:
    """Descobre o campo que liga o intersect/buffer de volta ao segmento."""
    nomes = [f.name for f in arcpy.ListFields(tabela)]
    for candidato in (
        'SEG_OID',
        'ORIG_FID',
        'ORIG_FID_1',
        'FID_mid_point',
        'FID_buffer_mid_point',
    ):
        if candidato in nomes:
            return candidato
    # fallback: procura campo que comece com ORIG_ ou FID_
    for nome in nomes:
        upper = nome.upper()
        if upper.startswith('ORIG_FID') or upper.startswith('FID_'):
            return nome
    raise ValueError(
        f'Não foi possível achar campo de ligação em {tabela}. Campos: {nomes}'
    )


def _where_excluir_lote(n_coletivo: str, quadra, lote: str) -> str:
    """Where que remove o próprio lote do intersect de vizinhos."""
    reurb = str(n_coletivo).strip().replace("'", "''")
    lote_txt = str(lote).strip().replace("'", "''")
    try:
        quadra_sql = str(int(str(quadra).strip()))
    except (TypeError, ValueError):
        q = str(quadra).strip().replace("'", "''")
        quadra_sql = f"'{q}'"
    return (
        f"n_coletivo = '{reurb}' AND quadra = {quadra_sql} "
        f"AND lote = '{lote_txt}'"
    )


def _formatar_codigo_ql(valor) -> str:
    """Normaliza lote/quadra para o padrão XX (ex.: 02, 11)."""
    if valor is None:
        return ''
    texto = str(valor).strip()
    if not texto or texto.lower() in ('<nulo>', 'none', 'null'):
        return ''
    if texto.isdigit():
        return texto.zfill(2)
    # Remove prefixo acidental L/Q se vier do cadastro
    if len(texto) >= 2 and texto[0].upper() in ('L', 'Q') and texto[1:].isdigit():
        return texto[1:].zfill(2)
    return texto


def _texto_lote_vizinho(lote_vizinho, quadra_vizinha=None) -> str:
    """Rótulo de lote vizinho no padrão institucional ``LOTE 02``."""
    lote_cod = _formatar_codigo_ql(lote_vizinho)
    if not lote_cod:
        return ''
    return f'LOTE {lote_cod.upper()}'


def _aceita_overlap(overlap_m: float, comprimento_segmento_m: float) -> bool:
    """True se a aresta compartilhada é frente real (não só canto)."""
    if overlap_m <= 0:
        return False
    if overlap_m >= OVERLAP_MINIMO_CONFRONTANTE_M:
        return True
    if comprimento_segmento_m <= 0:
        return False
    return overlap_m >= OVERLAP_MINIMO_FRACAO_SEGMENTO * comprimento_segmento_m


def _tipo_geometria(fc) -> str:
    """polygon, polyline ou point (minúsculo), vazio se não der para ler."""
    if arcpy is None or not fc:
        return ''
    try:
        return (arcpy.Describe(fc).shapeType or '').strip().lower()
    except Exception:
        return ''


def _buffer_m_externo(vizinhos_fc) -> float:
    """Linha (layer 1 atual) usa 5 m; polígono usa aresta compartilhada 0,5 m."""
    if _tipo_geometria(vizinhos_fc) == 'polyline':
        return BUFFER_CONFRONTANTE_EXTERNO_M
    return BUFFER_ARESTA_CONFRONTANTE_M


def _texto_info_lote(info_lote) -> tuple:
    """Monta ``LOTE XX`` e o overlap da aresta a partir do dict de ``_melhor_por_aresta``."""
    if not info_lote:
        return '', 0.0
    lote_v = info_lote.get('lote') or info_lote.get('LOTE')
    quadra_v = info_lote.get('quadra') or info_lote.get('QUADRA')
    if lote_v is None:
        for k, v in info_lote.items():
            if k.lower() == 'lote':
                lote_v = v
            elif k.lower() == 'quadra':
                quadra_v = v
    return _texto_lote_vizinho(lote_v, quadra_v), float(info_lote.get('_overlap') or 0)


def _texto_info_externo(info_ext) -> tuple:
    """Primeiro campo de nome do confrontante externo + overlap."""
    if not info_ext:
        return '', 0.0
    texto = ''
    for k, v in info_ext.items():
        if k.startswith('_'):
            continue
        if v is not None and str(v).strip():
            texto = str(v).strip()
            break
    return texto, float(info_ext.get('_overlap') or 0)


def resolver_confrontante_aresta(
    texto_eixo='',
    texto_lote='',
    overlap_lote_m=0.0,
    texto_externo='',
    overlap_externo_m=0.0,
    comprimento_m=0.0,
) -> str:
    """Confrontante da aresta P-n → P-n+1.

    Ordem do exemplo de lote: lote com frente real; Confrontante Externo
    (linha, hit no ponto médio); eixo só se os dois faltarem; lote de
    canto se ainda sobrar.
    """
    eixo = str(texto_eixo or '').strip()
    lote = str(texto_lote or '').strip()
    externo = str(texto_externo or '').strip()
    lote_e_frente = bool(lote) and _aceita_overlap(
        float(overlap_lote_m or 0), float(comprimento_m or 0)
    )
    if lote_e_frente:
        return lote
    if externo:
        return externo
    if eixo:
        return eixo
    return lote


def _comprimentos_segmentos(feicao_entrada) -> dict:
    """OBJECTID → comprimento (m)."""
    saida = {}
    with arcpy.da.SearchCursor(feicao_entrada, ['OID@', 'SHAPE@LENGTH']) as cur:
        for oid, leng in cur:
            saida[oid] = float(leng or 0)
    return saida


def _cosseno_paralelismo(vetor_a, vetor_b) -> float:
    """|cos θ| entre dois vetores 2D; 0 se algum for nulo."""
    ax, ay = vetor_a
    bx, by = vetor_b
    ma = math.hypot(ax, ay)
    mb = math.hypot(bx, by)
    if not ma or not mb:
        return 0.0
    return abs(ax * bx + ay * by) / (ma * mb)


def _tangente_segmento(linha) -> tuple:
    """Vetor tangente no meio do segmento."""
    antes = linha.positionAlongLine(0.45, True).firstPoint
    depois = linha.positionAlongLine(0.55, True).firstPoint
    return depois.X - antes.X, depois.Y - antes.Y


def _tangente_eixo(linha, distancia_m: float) -> tuple:
    """Tangente local do eixo no ponto mais próximo ao segmento."""
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


_SONDAS_NORMAL_EXTERNA = (0.5, 1, 2, 5, 10, 20, 50)


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


def _normal_externa_segmento(linha, anel, centroide) -> tuple:
    """Vetor unitário perpendicular à aresta, apontando para fora do lote."""
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
        except Exception:
            pass

    if centroide is not None:
        for candidato in ((nx, ny), (-nx, -ny)):
            if (
                candidato[0] * (meio.X - centroide.X)
                + candidato[1] * (meio.Y - centroide.Y)
            ) > 0:
                return candidato
    return nx, ny


def _ler_segmentos_ordenados(feicao_entrada) -> list:
    """Segmentos do anel na ordem do memorial (campo ``de`` quando existir)."""
    campos = [f.name for f in arcpy.ListFields(feicao_entrada)]
    tem_de = 'de' in campos
    leitura = ['OID@', 'SHAPE@']
    if tem_de:
        leitura.append('de')
    sr = arcpy.Describe(feicao_entrada).spatialReference
    itens = []
    with arcpy.da.SearchCursor(feicao_entrada, leitura) as cur:
        for row in cur:
            item = {'oid': row[0], 'shape': row[1], 'sr': sr}
            if tem_de:
                item['de'] = row[2]
            itens.append(item)
    if tem_de:
        def _ordem(item):
            try:
                return int(str(item.get('de') or '').split('-')[-1])
            except (TypeError, ValueError):
                return item['oid']

        itens.sort(key=_ordem)
    else:
        itens.sort(key=lambda item: item['oid'])
    return itens


def _montar_anel_de_segmentos(segmentos, sr):
    """Polígono do contorno a partir dos segmentos ordenados (fallback)."""
    if len(segmentos) < 3:
        return None
    pontos = []
    for seg in segmentos:
        linha = seg.get('shape')
        if linha is None or linha.length == 0:
            continue
        p = linha.firstPoint
        pontos.append(arcpy.Point(p.X, p.Y))
    if len(pontos) < 3:
        return None
    try:
        return arcpy.Polygon(arcpy.Array(pontos), sr)
    except Exception:
        return None


def _poligono_do_lote(poligono_lote, sr):
    """Geometria original do lote, já no SR dos segmentos."""
    if not poligono_lote:
        return None
    with arcpy.da.SearchCursor(poligono_lote, ['SHAPE@']) as cur:
        row = next(cur, None)
    if not row or row[0] is None:
        return None
    geom = row[0]
    wkid_g = getattr(geom.spatialReference, 'factoryCode', None)
    wkid_s = getattr(sr, 'factoryCode', None)
    if wkid_g != wkid_s:
        geom = geom.projectAs(sr)
    return geom


def _avaliar_candidatos_eixo(
    seg,
    eixos,
    anel,
    centroide,
    par_minimo: float,
    distancia_max: float = None,
) -> list:
    """Candidatos de eixo à frente da testada (lado externo + distância + paralelismo)."""
    if distancia_max is None:
        distancia_max = DISTANCIA_MAX_EIXO_M
    linha = seg.get('shape')
    if linha is None or linha.length == 0:
        return []

    normal = _normal_externa_segmento(linha, anel, centroide)
    meio = linha.positionAlongLine(0.5, True).firstPoint
    tangente_seg = _tangente_segmento(linha)
    aprovados = []

    for info in eixos.values():
        eixo_shape = info['shape']
        proximo_geom, dist_along, dist_from, _ = eixo_shape.queryPointAndDistance(meio)
        proximo = proximo_geom.firstPoint
        vx = proximo.X - meio.X
        vy = proximo.Y - meio.Y
        dist_normal = vx * normal[0] + vy * normal[1]
        if dist_normal <= 0 or dist_from > distancia_max:
            continue
        tangente_eixo = _tangente_eixo(eixo_shape, dist_along)
        par = _cosseno_paralelismo(tangente_seg, tangente_eixo)
        if par < par_minimo:
            continue
        aprovados.append((par, float(dist_from), info['logradouro']))

    return aprovados


def _escolher_melhor_eixo(aprovados: list):
    """Maior paralelismo; empate usa a menor distância à polilinha."""
    if not aprovados:
        return None
    return max(aprovados, key=lambda item: (item[0], -item[1]))[2]


def _comprimento_segmento(seg) -> float:
    """Comprimento da geometria do segmento em metros."""
    if not seg:
        return 0.0
    linha = seg.get('shape')
    if linha is None:
        return 0.0
    return float(getattr(linha, 'length', 0) or 0)


def _e_quebra_abrupta(seg, prev, nxt) -> bool:
    """Segmento curto com mudança de direção ~90° em relação a um vizinho."""
    comprimento = _comprimento_segmento(seg)
    if comprimento <= 0 or comprimento > COMPRIMENTO_MAX_QUEBRA_ABRUPTA_M:
        return False
    linha = seg.get('shape')
    if linha is None:
        return False
    tangente_atual = _tangente_segmento(linha)
    if not tangente_atual[0] and not tangente_atual[1]:
        return False
    for vizinho in (prev, nxt):
        linha_v = vizinho.get('shape') if vizinho else None
        if linha_v is None or getattr(linha_v, 'length', 0) == 0:
            continue
        tangente_v = _tangente_segmento(linha_v)
        if _cosseno_paralelismo(tangente_atual, tangente_v) <= COSSENO_MAX_QUEBRA_ABRUPTA:
            return True
    return False


def _herdar_eixo_vizinho_mais_longo(
    melhor: dict,
    ordem_oids: list,
    segmentos_por_oid: dict,
    oids_quebra: set,
) -> int:
    """Herda logradouro do vizinho de maior comprimento nas quebras sem eixo."""
    n = len(ordem_oids)
    herdados = 0
    for i, oid in enumerate(ordem_oids):
        if oid not in oids_quebra or melhor.get(oid):
            continue
        prev_oid = ordem_oids[(i - 1) % n]
        next_oid = ordem_oids[(i + 1) % n]
        candidatos = []
        prev_log = melhor.get(prev_oid)
        next_log = melhor.get(next_oid)
        if prev_log:
            candidatos.append((
                _comprimento_segmento(segmentos_por_oid.get(prev_oid)),
                True,
                prev_log,
            ))
        if next_log:
            candidatos.append((
                _comprimento_segmento(segmentos_por_oid.get(next_oid)),
                False,
                next_log,
            ))
        if not candidatos:
            continue
        candidatos.sort(key=lambda item: (-item[0], 0 if item[1] else 1))
        melhor[oid] = candidatos[0][2]
        herdados += 1
    return herdados


def propagar_eixo_entre_vizinhos(
    por_eixo: dict,
    ordem_oids: list,
    oids_pendentes=None,
) -> dict:
    """Herda logradouro quando vizinhos consecutivos concordam (chanfros).

    Só preenche OIDs pendentes: lado já resolvido (lote/externo) não
    serve de fonte nem de destino.
    """
    n = len(ordem_oids)
    if n < 3:
        return dict(por_eixo)
    resultado = dict(por_eixo)
    oids_set = set(oids_pendentes) if oids_pendentes is not None else None
    for _ in range(n):
        alterou = False
        for i in range(n):
            oid = ordem_oids[i]
            if resultado.get(oid):
                continue
            if oids_set is not None and oid not in oids_set:
                continue
            prev_log = resultado.get(ordem_oids[(i - 1) % n])
            next_log = resultado.get(ordem_oids[(i + 1) % n])
            if prev_log and prev_log == next_log:
                resultado[oid] = prev_log
                alterou = True
        if not alterou:
            break
    return resultado


def _melhor_eixo_por_aresta(
    feicao_entrada,
    eixo_fc,
    oids_pendentes=None,
    poligono_lote=None,
) -> dict:
    """Eixo à frente da testada só nos lados sem lote e sem externo.

    Quebra abrupta (≤5 m e ~90°) busca até 10 m e, se vazio, herda do
    vizinho mais longo que já tenha eixo. Propagação só entre pendentes.
    """
    segmentos = _ler_segmentos_ordenados(feicao_entrada)
    if not segmentos:
        return {}

    sr = segmentos[0]['sr']
    anel = _poligono_do_lote(poligono_lote, sr) or _montar_anel_de_segmentos(
        segmentos, sr
    )
    centroide = anel.centroid if anel is not None else None
    oids_set = set(oids_pendentes) if oids_pendentes is not None else None
    ordem_oids = [s['oid'] for s in segmentos]

    eixos = {}
    with arcpy.da.SearchCursor(eixo_fc, ['OID@', 'SHAPE@', 'logradouro']) as cur:
        for oid, shape, logradouro in cur:
            if logradouro and str(logradouro).strip():
                eixos[oid] = {
                    'shape': shape,
                    'logradouro': str(logradouro).strip(),
                }

    if not eixos:
        arcpy.AddWarning('Nenhum eixo viário com logradouro na área recortada.')
        return {}

    melhor = {}
    segmentos_por_oid = {seg['oid']: seg for seg in segmentos}
    oids_quebra = set()
    tier_contagem = {'estrito': 0, 'relaxado': 0, 'ultimo': 0}
    quebra_contagem = {'total': 0, 'eixo_10m': 0, 'herdado': 0}
    tiers = (
        ('estrito', PARALELISMO_MINIMO_EIXO),
        ('relaxado', PARALELISMO_MINIMO_EIXO_FALLBACK),
        ('ultimo', PARALELISMO_MINIMO_EIXO_ULTIMO),
    )
    n_segmentos = len(segmentos)

    for i, seg in enumerate(segmentos):
        seg_oid = seg['oid']
        if oids_set is not None and seg_oid not in oids_set:
            continue

        prev_seg = segmentos[(i - 1) % n_segmentos]
        next_seg = segmentos[(i + 1) % n_segmentos]
        e_quebra = _e_quebra_abrupta(seg, prev_seg, next_seg)
        distancia_max = (
            DISTANCIA_MAX_EIXO_QUEBRA_M if e_quebra else DISTANCIA_MAX_EIXO_M
        )
        if e_quebra:
            oids_quebra.add(seg_oid)
            quebra_contagem['total'] += 1

        logradouro = None
        tier_usado = None
        for nome_tier, par_min in tiers:
            aprovados = _avaliar_candidatos_eixo(
                seg,
                eixos,
                anel,
                centroide,
                par_min,
                distancia_max=distancia_max,
            )
            logradouro = _escolher_melhor_eixo(aprovados)
            if logradouro:
                tier_usado = nome_tier
                break

        if logradouro:
            melhor[seg_oid] = logradouro
            if e_quebra:
                quebra_contagem['eixo_10m'] += 1
            else:
                tier_contagem[tier_usado] += 1

    quebra_contagem['herdado'] = _herdar_eixo_vizinho_mais_longo(
        melhor,
        ordem_oids,
        segmentos_por_oid,
        oids_quebra,
    )

    antes_prop = len(melhor)
    melhor = propagar_eixo_entre_vizinhos(
        melhor,
        ordem_oids,
        oids_pendentes=oids_pendentes,
    )
    propagados = len(melhor) - antes_prop
    total_pendentes = len(oids_set) if oids_set is not None else len(ordem_oids)

    arcpy.AddMessage(
        f'Eixo viário (testada): {tier_contagem["estrito"]} estrito, '
        f'{tier_contagem["relaxado"]} relaxado, {tier_contagem["ultimo"]} último '
        f'recurso; {quebra_contagem["total"]} quebra abrupta '
        f'({quebra_contagem["eixo_10m"]} com eixo em 10 m, '
        f'{quebra_contagem["herdado"]} herdado do vizinho); '
        f'{propagados} por propagação; '
        f'{max(0, total_pendentes - len(melhor))} sem candidato '
        f'({total_pendentes} segmentos elegíveis).'
    )
    return melhor


def _melhor_por_aresta(
    feicao_entrada,
    vizinhos_fc,
    campos_chave: list,
    where_excluir: str = None,
    buffer_m=None,
    prefixo='aresta',
) -> dict:
    """Para cada segmento, escolhe o vizinho com maior overlap de aresta.

    O overlap é o comprimento da **linha** dentro do buffer do vizinho
    (metros de frente). Buffer no vizinho (polígono ou linha) + intersect
    com a aresta evita o falso positivo do canto: o perímetro do polígono
    de interseção inflava o score e o lote do vértice seguinte ganhava.

    Args:
        feicao_entrada: segmentos do perímetro.
        vizinhos_fc: polígonos ou linhas (lotes ou Confrontante Externo).
        campos_chave: campos a agregar (ex.: ['lote','quadra'] ou ['nome']).
        where_excluir: remove o próprio lote do intersect.
        buffer_m: largura do buffer do vizinho (padrão: lote vizinho).
        prefixo: nomes únicos no scratch (lote e externo na mesma execução).

    Returns:
        dict OID → dict com chaves dos campos + ``_overlap``.
    """
    from collections import defaultdict

    if buffer_m is None:
        buffer_m = BUFFER_ARESTA_CONFRONTANTE_M
    linhas = _criar_midpoints(feicao_entrada, f'{prefixo}_seg')
    # Buffer no vizinho, não na aresta: o intersect volta polilinha e
    # SHAPE@LENGTH é o comprimento da frente compartilhada.
    buffer = arcpy.analysis.PairwiseBuffer(
        in_features=vizinhos_fc,
        out_feature_class=_scratch(f'{prefixo}_viz_buf'),
        buffer_distance_or_field=f'{buffer_m} Meters',
        dissolve_option='NONE',
        method='PLANAR',
    )
    intersect = arcpy.analysis.PairwiseIntersect(
        in_features=[linhas, buffer],
        out_feature_class=_scratch(f'{prefixo}_int'),
    )
    if where_excluir:
        sel = arcpy.management.SelectLayerByAttribute(
            in_layer_or_view=intersect,
            selection_type='NEW_SELECTION',
            where_clause=where_excluir,
        )
        arcpy.management.DeleteRows(sel)
        arcpy.management.SelectLayerByAttribute(
            in_layer_or_view=intersect,
            selection_type='CLEAR_SELECTION',
        )

    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(intersect)}
    campo_orig = _campo_join_origem(intersect)
    campos_reais = []
    for c in campos_chave:
        if c.lower() in nomes:
            campos_reais.append(nomes[c.lower()])
    if not campos_reais:
        return {}

    # ORIG_FID → chave → overlap
    scores = defaultdict(lambda: defaultdict(float))
    leitura = [campo_orig, 'SHAPE@LENGTH'] + campos_reais
    with arcpy.da.SearchCursor(intersect, leitura) as cur:
        for row in cur:
            oid = row[0]
            leng = float(row[1] or 0)
            chave = tuple(row[2 + i] for i in range(len(campos_reais)))
            if any(v is None or str(v).strip() == '' for v in chave):
                continue
            scores[oid][chave] += leng

    comprimentos = _comprimentos_segmentos(feicao_entrada)
    melhor = {}
    for oid, candidatos in scores.items():
        chave, overlap = max(candidatos.items(), key=lambda item: item[1])
        if not _aceita_overlap(overlap, comprimentos.get(oid, 0)):
            continue
        registro = {campos_reais[i]: chave[i] for i in range(len(campos_reais))}
        registro['_overlap'] = overlap
        melhor[oid] = registro
    return melhor


def _melhor_por_buffer_ponto_medio(
    feicao_entrada,
    vizinhos_fc,
    campos_chave: list,
    buffer_m,
    prefixo='mid_ext',
    where_excluir: str = None,
) -> dict:
    """Casa vizinho no ponto médio da aresta (Confrontante Externo em linha: 5 m)."""
    from collections import defaultdict

    pontos = _criar_pontos_medios(feicao_entrada, f'{prefixo}_mid')
    buffer = arcpy.analysis.PairwiseBuffer(
        in_features=pontos,
        out_feature_class=_scratch(f'{prefixo}_mid_buf'),
        buffer_distance_or_field=f'{buffer_m} Meters',
        dissolve_option='NONE',
        method='PLANAR',
    )
    intersect = arcpy.analysis.PairwiseIntersect(
        in_features=[buffer, vizinhos_fc],
        out_feature_class=_scratch(f'{prefixo}_mid_int'),
    )
    if where_excluir:
        sel = arcpy.management.SelectLayerByAttribute(
            in_layer_or_view=intersect,
            selection_type='NEW_SELECTION',
            where_clause=where_excluir,
        )
        arcpy.management.DeleteRows(sel)
        arcpy.management.SelectLayerByAttribute(
            in_layer_or_view=intersect,
            selection_type='CLEAR_SELECTION',
        )

    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(intersect)}
    try:
        campo_orig = _campo_join_origem(intersect)
    except ValueError:
        return {}
    campos_reais = []
    for c in campos_chave:
        if c.lower() in nomes:
            campos_reais.append(nomes[c.lower()])
    if not campos_reais:
        return {}

    scores = defaultdict(lambda: defaultdict(float))
    leitura = [campo_orig, 'SHAPE@LENGTH'] + campos_reais
    with arcpy.da.SearchCursor(intersect, leitura) as cur:
        for row in cur:
            oid = row[0]
            leng = float(row[1] or 0)
            chave = tuple(row[2 + i] for i in range(len(campos_reais)))
            if any(v is None or str(v).strip() == '' for v in chave):
                continue
            scores[oid][chave] += leng

    melhor = {}
    for oid, candidatos in scores.items():
        chave, overlap = max(candidatos.items(), key=lambda item: item[1])
        registro = {campos_reais[i]: chave[i] for i in range(len(campos_reais))}
        registro['_overlap'] = overlap
        melhor[oid] = registro
    return melhor


def confrontantes_lote(
    feicao_entrada: os.PathLike,
    n_coletivo: str,
    quadra,
    lote: str,
    lote_feicoes: os.PathLike,
    confrontante_feicoes: os.PathLike,
    eixo_viario: os.PathLike,
    poligono_lote=None,
) -> None:
    """Confrontantes na escala de lote (padrão institucional).

    1) lote vizinho com frente compartilhada (``LOTE 02``)
    2) Confrontante Externo (campo nome; linha, buffer 5 m no ponto médio)
    3) eixo viário só nos lados sem lote e sem externo
    """
    if arcpy is None:
        raise RuntimeError('arcpy necessário para calcular confrontantes.')

    arcpy.AddMessage(
        'Confrontantes do lote: lote → Confrontante Externo (5 m no '
        'ponto médio) → eixo só nos lados que restarem'
    )
    reurb = str(n_coletivo).strip().replace("'", "''")
    sr_lote = arcpy.Describe(feicao_entrada).spatialReference
    campos_ext = {
        f.name.casefold() for f in arcpy.ListFields(confrontante_feicoes)
    }
    if 'nome' not in campos_ext:
        arcpy.AddWarning(
            "Camada Confrontante Externo sem campo 'nome'; "
            "matrículas externas serão ignoradas."
        )
    lotes_local = _materializar_projetado(
        lote_feicoes,
        'lotes_confrontantes_local',
        sr_lote,
        where_clause=f"n_coletivo = '{reurb}'",
    )
    conf_local = _materializar_entorno(
        confrontante_feicoes,
        'confrontante_externo_local',
        sr_lote,
        feicao_entrada,
        BUFFER_BUSCA_EIXO_M,
    )
    eixo_local = _materializar_projetado(
        eixo_viario,
        'eixo_viario_local',
        sr_lote,
    )
    eixo_local = _recortar_eixo_ao_lote(eixo_local, feicao_entrada)

    por_lote = _melhor_por_aresta(
        feicao_entrada,
        lotes_local,
        campos_chave=['lote', 'quadra'],
        where_excluir=_where_excluir_lote(n_coletivo, quadra, lote),
        prefixo='conf_lote',
    )
    n_conf = int(arcpy.management.GetCount(conf_local)[0])
    tipo_ext = _tipo_geometria(conf_local) or 'desconhecido'
    arcpy.AddMessage(
        f'Confrontante Externo materializado: {n_conf} feição(ões) '
        f'(geometria {tipo_ext}, buffer {BUFFER_CONFRONTANTE_EXTERNO_M} m '
        f'no ponto médio).'
    )
    if n_conf == 0:
        por_externo = {}
    elif tipo_ext == 'polygon':
        por_externo = _melhor_por_aresta(
            feicao_entrada,
            conf_local,
            campos_chave=['nome'],
            buffer_m=BUFFER_ARESTA_CONFRONTANTE_M,
            prefixo='conf_ext',
        )
    else:
        por_externo = _melhor_por_buffer_ponto_medio(
            feicao_entrada,
            conf_local,
            campos_chave=['nome'],
            buffer_m=BUFFER_CONFRONTANTE_EXTERNO_M,
            prefixo='conf_ext',
        )
    arcpy.AddMessage(
        f'Confrontante Externo casado em {len(por_externo)} segmento(s).'
    )

    oids_todos = list(_comprimentos_segmentos(feicao_entrada))
    oids_pendentes = [
        oid for oid in oids_todos
        if oid not in por_lote and oid not in por_externo
    ]
    por_eixo = _melhor_eixo_por_aresta(
        feicao_entrada,
        eixo_local,
        oids_pendentes=oids_pendentes,
        poligono_lote=poligono_lote,
    )

    arcpy.management.AddField(
        in_table=feicao_entrada,
        field_name='confrontantes',
        field_type='TEXT',
        field_alias='confrontantes',
        field_length=120,
    )

    comprimentos = _comprimentos_segmentos(feicao_entrada)
    identificados = 0
    padrao = 0
    with arcpy.da.UpdateCursor(feicao_entrada, ['OID@', 'confrontantes']) as cur:
        for oid, _ in cur:
            texto_lote, overlap_lote = _texto_info_lote(por_lote.get(oid))
            texto_ext, overlap_ext = _texto_info_externo(por_externo.get(oid))
            texto = resolver_confrontante_aresta(
                texto_eixo=por_eixo.get(oid) or '',
                texto_lote=texto_lote,
                overlap_lote_m=overlap_lote,
                texto_externo=texto_ext,
                overlap_externo_m=overlap_ext,
                comprimento_m=comprimentos.get(oid, 0),
            )
            if texto:
                cur.updateRow([oid, texto])
                identificados += 1
            else:
                cur.updateRow([oid, CONFRONTANTE_PADRAO])
                padrao += 1

    arcpy.AddMessage(
        f'Segmentos com confrontante identificado: {identificados}; '
        f'com padrão "{CONFRONTANTE_PADRAO}": {padrao} '
        f'(régua overlap ≥{OVERLAP_MINIMO_CONFRONTANTE_M} m ou '
        f'≥{int(OVERLAP_MINIMO_FRACAO_SEGMENTO * 100)}% da frente)'
    )
    _aplicar_absorcao_confrontantes_curtos(feicao_entrada)


def confrontantes(
    feicao_entrada: os.PathLike,
    n_coletivo: str,
    bairro_feicoes: os.PathLike,
    confrontante_feicoes: os.PathLike,
    eixo_viario: os.PathLike
) -> None:
    """
    Preenche confrontantes na tabela de atributos da feição de entrada.

    Ordem de prioridade do texto em 'confrontantes':
    1) Confrontante Externo (FeatureServer/1, campo nome)
    2) bairro vizinho (campo nome)
    3) eixo viário (campo logradouro)
    """
    if arcpy is None:
        raise RuntimeError('arcpy necessário para calcular confrontantes.')
    arcpy.AddMessage(
        f'Confrontante Externo na fonte: {confrontante_feicoes}'
    )

    # Materializa camadas remotas; confrontante/eixo filtrados perto do perímetro
    conf_local = _materializar(confrontante_feicoes, 'confrontante_externo_local')
    eixo_local = _materializar(eixo_viario, 'eixo_viario_local')
    n_conf = int(arcpy.management.GetCount(conf_local)[0])
    tipo_ext = _tipo_geometria(conf_local) or 'desconhecido'
    arcpy.AddMessage(
        f'Confrontante Externo materializado: {n_conf} feição(ões) '
        f'(geometria {tipo_ext}).'
    )

    mid_point = _criar_midpoints(feicao_entrada, 'mid_point')

    # GEODESIC: perímetro está em coordenadas geográficas (SIRGAS 2000)
    buffer = arcpy.analysis.PairwiseBuffer(
        in_features=mid_point,
        out_feature_class=_scratch('buffer_mid_point'),
        buffer_distance_or_field='5 Meters',
        dissolve_option='NONE',
        method='PLANAR'
    )

    # ---- Bairros vizinhos ----
    intersect_bairro = arcpy.analysis.PairwiseIntersect(
        in_features=[buffer, bairro_feicoes],
        out_feature_class=_scratch('intersect_bairro')
    )
    select_attr = arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=intersect_bairro,
        selection_type='NEW_SELECTION',
        where_clause=f"n_coletivo = '{n_coletivo}'"
    )
    arcpy.management.DeleteRows(select_attr)
    arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=intersect_bairro,
        selection_type='CLEAR_SELECTION'
    )
    campo_bairro = _campo_join_origem(intersect_bairro)
    arcpy.management.JoinField(
        in_data=feicao_entrada,
        in_field='OBJECTID',
        join_table=intersect_bairro,
        join_field=campo_bairro,
        fields=['nome']
    )

    # ---- Confrontante Externo (layer 1) ----
    intersect_confrontantes = arcpy.analysis.PairwiseIntersect(
        in_features=[buffer, conf_local],
        out_feature_class=_scratch('intersect_confrontantes')
    )
    n_hit = int(arcpy.management.GetCount(intersect_confrontantes)[0])
    arcpy.AddMessage(
        f'Interseções com Confrontante Externo: {n_hit}'
    )

    select_attr = arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=intersect_confrontantes,
        selection_type='NEW_SELECTION',
        where_clause='nome IS NULL'
    )
    arcpy.management.DeleteRows(select_attr)
    arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=intersect_confrontantes,
        selection_type='CLEAR_SELECTION'
    )

    if int(arcpy.management.GetCount(intersect_confrontantes)[0]) > 0:
        campo_conf = _campo_join_origem(intersect_confrontantes)
        arcpy.management.JoinField(
            in_data=feicao_entrada,
            in_field='OBJECTID',
            join_table=intersect_confrontantes,
            join_field=campo_conf,
            fields=['nome']
        )
    else:
        arcpy.AddWarning(
            'Nenhum Confrontante Externo intersectou o perímetro '
            '(buffer 5 m). Verifique se há feições próximas ao núcleo.'
        )

    # ---- Eixo viário mais próximo ----
    mid_com_eixo = _scratch('mid_com_eixo')
    _recriar_fc(mid_com_eixo)
    arcpy.analysis.SpatialJoin(
        target_features=mid_point,
        join_features=eixo_local,
        out_feature_class=mid_com_eixo,
        join_operation='JOIN_ONE_TO_ONE',
        join_type='KEEP_ALL',
        match_option='CLOSEST',
        distance_field_name='NEAR_DIST',
        search_radius='50 Meters'
    )

    select_null_lote = arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=feicao_entrada,
        selection_type='NEW_SELECTION',
        where_clause='nome IS NULL'
    )
    arcpy.management.JoinField(
        in_data=select_null_lote,
        in_field='OBJECTID',
        join_table=mid_com_eixo,
        join_field='ORIG_FID',
        fields=['logradouro']
    )
    arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=feicao_entrada,
        selection_type='CLEAR_SELECTION'
    )

    arcpy.management.AddField(
        in_table=feicao_entrada,
        field_name='confrontantes',
        field_type='TEXT',
        field_alias='confrontantes',
        field_length=120,
    )

    # nome = bairro vizinho; nome_1 = confrontante externo (2º JoinField).
    # Matrícula/externo ganha do bairro vizinho quando os dois encostam.
    campos = [f.name for f in arcpy.ListFields(feicao_entrada)]
    tem_nome1 = 'nome_1' in campos
    tem_logradouro = 'logradouro' in campos

    if tem_nome1:
        arcpy.management.CalculateFields(
            in_table=feicao_entrada,
            expression_type='PYTHON3',
            fields=[
                ['confrontantes', '!nome_1!', 'nome_1 IS NOT NULL'],
            ]
        )
    arcpy.management.CalculateFields(
        in_table=feicao_entrada,
        expression_type='PYTHON3',
        fields=[
            ['confrontantes', '!nome!', 'confrontantes IS NULL AND nome IS NOT NULL'],
        ]
    )
    if tem_logradouro:
        arcpy.management.CalculateFields(
            in_table=feicao_entrada,
            expression_type='PYTHON3',
            fields=[
                ['confrontantes', '!logradouro!', 'confrontantes IS NULL'],
            ]
        )

    identificados = 0
    padrao = 0
    with arcpy.da.UpdateCursor(feicao_entrada, ['confrontantes']) as cur:
        for row in cur:
            valor = (row[0] or '').strip() if row[0] else ''
            if valor:
                identificados += 1
            else:
                row[0] = CONFRONTANTE_PADRAO
                cur.updateRow(row)
                padrao += 1
    arcpy.AddMessage(
        f'Segmentos com confrontante identificado: {identificados}; '
        f'com padrão "{CONFRONTANTE_PADRAO}": {padrao}'
    )

    _aplicar_absorcao_confrontantes_curtos(feicao_entrada)
