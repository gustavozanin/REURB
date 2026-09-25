#-*- coding: utf-8 -*-

"""Identifica confrontantes sem ferramentas de licença Advanced."""

import os
import arcpy


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
    """Cria pontos no meio de cada segmento (substitui FeatureVerticesToPoints MID)."""
    desc = arcpy.Describe(feicao_entrada)
    sr = desc.spatialReference
    out_fc = _scratch(out_name)
    _recriar_fc(out_fc)

    arcpy.management.CreateFeatureclass(
        out_path=arcpy.env.scratchGDB,
        out_name=out_name,
        geometry_type='POINT',
        spatial_reference=sr
    )
    arcpy.management.AddField(out_fc, 'ORIG_FID', 'LONG')

    with arcpy.da.SearchCursor(feicao_entrada, ['OID@', 'SHAPE@']) as scur:
        with arcpy.da.InsertCursor(out_fc, ['SHAPE@', 'ORIG_FID']) as icur:
            for oid, shape in scur:
                if shape is None or shape.length == 0:
                    continue
                mid = shape.positionAlongLine(0.5, True)
                icur.insertRow([mid.firstPoint, oid])

    return out_fc


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
        method='GEODESIC'
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
        field_alias='confrontantes'
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

    preenchidos = 0
    with arcpy.da.SearchCursor(feicao_entrada, ['confrontantes']) as cur:
        for row in cur:
            if row[0]:
                preenchidos += 1
    arcpy.AddMessage(
        f'Segmentos com confrontante preenchido: {preenchidos}'
    )
