#-*- coding: utf-8 -*-

"""Identifica confrontantes sem ferramentas de licença Advanced."""

import os
import re

try:
    import arcpy
except ImportError:
    arcpy = None

from collections import defaultdict

from constantes import (
    COMPRIMENTO_MAX_ABSORCAO_CONFRONTANTE_M,
    CONFRONTANTE_PADRAO,
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

    with arcpy.da.SearchCursor(feicao_entrada, ['OID@', 'SHAPE@']) as scur:
        with arcpy.da.InsertCursor(out_fc, ['SHAPE@', 'ORIG_FID']) as icur:
            for oid, shape in scur:
                if shape is None or shape.length == 0:
                    continue
                icur.insertRow([shape, oid])

    return out_fc


def _melhor_nome_por_comprimento(intersect_fc) -> dict:
    """OID do segmento → nome do vizinho com maior trecho compartilhado."""
    campo_orig = _campo_join_origem(intersect_fc)
    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(intersect_fc)}
    campo_nome = nomes.get('nome')
    if not campo_nome:
        return {}
    scores = defaultdict(lambda: ('', 0.0))
    with arcpy.da.SearchCursor(
        intersect_fc, [campo_orig, campo_nome, 'SHAPE@LENGTH']
    ) as cur:
        for oid, nome, leng in cur:
            if oid is None or not str(nome or '').strip():
                continue
            comprimento = float(leng or 0)
            atual = scores[oid]
            if comprimento > atual[1]:
                scores[oid] = (str(nome).strip(), comprimento)
    return {oid: nome for oid, (nome, _) in scores.items() if nome}


def _campo_join_origem(tabela) -> str:
    """Descobre o campo que liga o intersect/buffer de volta ao segmento."""
    nomes = [f.name for f in arcpy.ListFields(tabela)]
    for candidato in ('ORIG_FID', 'ORIG_FID_1', 'FID_mid_point', 'FID_buffer_mid_point'):
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
    try:
        tipo_ext = (arcpy.Describe(conf_local).shapeType or '').lower()
    except Exception:
        tipo_ext = 'desconhecido'
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

    externo_por_oid = {}
    if int(arcpy.management.GetCount(intersect_confrontantes)[0]) > 0:
        externo_por_oid = _melhor_nome_por_comprimento(intersect_confrontantes)
        arcpy.AddMessage(
            f'Confrontante Externo casado em {len(externo_por_oid)} '
            f'segmento(s) (maior trecho compartilhado).'
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

    campos = [f.name for f in arcpy.ListFields(feicao_entrada)]
    tem_logradouro = 'logradouro' in campos
    leitura = ['OID@', 'nome']
    if tem_logradouro:
        leitura.append('logradouro')
    leitura.append('confrontantes')

    identificados = 0
    padrao = 0
    with arcpy.da.UpdateCursor(feicao_entrada, leitura) as cur:
        for row in cur:
            oid = row[0]
            bairro = str(row[1] or '').strip()
            logradouro = ''
            if tem_logradouro:
                logradouro = str(row[2] or '').strip()
            valor = (
                externo_por_oid.get(oid)
                or bairro
                or logradouro
                or CONFRONTANTE_PADRAO
            )
            row[-1] = valor
            cur.updateRow(row)
            if valor == CONFRONTANTE_PADRAO:
                padrao += 1
            else:
                identificados += 1
    arcpy.AddMessage(
        f'Segmentos com confrontante identificado: {identificados}; '
        f'com padrão "{CONFRONTANTE_PADRAO}": {padrao}'
    )

    _aplicar_absorcao_confrontantes_curtos(feicao_entrada)
