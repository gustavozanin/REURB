# -*- coding: utf-8 -*-

import arcpy

from sql_utils import clausula_n_coletivo

_LIMITE_DETALHES = 10


def _listar_fora(layer, campos):
    """
    Lista até N registros selecionados para mensagem de erro.
    """
    detalhes = []
    with arcpy.da.SearchCursor(layer, campos) as cursor:
        for row in cursor:
            detalhes.append(', '.join(f'{campo}={valor}' for campo, valor in zip(campos, row)))
            if len(detalhes) >= _LIMITE_DETALHES:
                break
    return detalhes


def _verificar_contencao(layer, nucleo_layer, where_clause, camada_nome, campos_log):
    """
    Verifica se as quadras e lotes estão dentro do núcleo indicado pelo número do reurb coletivo.
    """
    arcpy.SelectLayerByLocation_management(
        in_layer=layer,
        overlap_type='HAVE_THEIR_CENTER_IN',
        select_features=nucleo_layer,
        selection_type='SUBSET_SELECTION',
        invert_spatial_relationship='INVERT'
    )
    contagem = int(arcpy.GetCount_management(in_rows=layer)[0])

    if contagem > 0:
        detalhes = _listar_fora(layer, campos_log)
        mensagem = (
            f'{contagem} {camada_nome} estão fora do perímetro do núcleo.'
        )
        if detalhes:
            mensagem += f' Exemplos: {"; ".join(detalhes)}'
        arcpy.AddError(mensagem)
        arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=layer,
            selection_type='NEW_SELECTION',
            where_clause=where_clause
        )
        return False

    arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=layer,
        selection_type='NEW_SELECTION',
        where_clause=where_clause
    )
    return True


def check_contencao_espacial(
    nucleo_layer,
    quadras_layer,
    lotes_layer,
    numero_reurb_coletivo: str
) -> bool:
    """
    Verifica se quadras e lotes estão completamente dentro do perímetro do núcleo.

    Args:
        nucleo_layer: Feature layer do bairro (núcleo) selecionado.
        quadras_layer: Feature layer de quadras filtrado por n_coletivo.
        lotes_layer: Feature layer de lotes filtrado por n_coletivo.
        numero_reurb_coletivo: Valor de n_coletivo para restaurar seleções.

    Returns:
        True se todas as feições estiverem contidas no núcleo.
    """
    where_clause = clausula_n_coletivo(numero_reurb_coletivo)

    if not _verificar_contencao(
        quadras_layer, nucleo_layer, where_clause, 'quadras', ['quadra']
    ):
        return False

    if not _verificar_contencao(
        lotes_layer, nucleo_layer, where_clause, 'lotes', ['quadra', 'lote']
    ):
        return False

    return True
