# -*- coding: utf-8 -*-

import os
import arcpy

def check_quadra(
    lotes_features: os.PathLike,
    quadra_features: os.PathLike,
    numero_reurb_coletivo: str,
    quadra: int
) -> bool:
    """
    Verifica se o preenchimento do campo quadra dos lotes está correto.

    -------
    Args:
        lotes_features(os.PathLike):
            Caminho para o shapefile dos lotes.
        quadra_features(os.PathLike):
            Caminho para o shapefile das quadras.
        numero_reurb_coletivo(str):
            Número do REURB coletivo.
        quadra(int):
            Número da quadra.

    -------
    Returns:
        bool:
            True se a quadra está preenchida corretamente, False caso contrário.
    """
    try:
        select_quadra = arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=quadra_features,
            selection_type='NEW_SELECTION',
            where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\' AND quadra = {quadra}'
        )

        if int(select_quadra[1]) == 0:
            return False

        select_lote = arcpy.SelectLayerByLocation_management(
            in_layer=lotes_features,
            overlap_type='INTERSECT',
            select_features=select_quadra,
            selection_type='NEW_SELECTION'
        )

        with arcpy.da.SearchCursor(select_quadra, ['quadra']) as cursor:
            for row in cursor:
                quadra_number = row[0]

        # with arcpy.da.UpdateCursor(select_lote, ['quadra']) as cursor:
        #     for row in cursor:
        #         lote_quadra = row[0]
        #         if lote_quadra != quadra_number:
        #             row[0] = quadra_number
        #             arcpy.AddMessage(f'Lote {row[0]} não possui a quadra {quadra_number}, atualizando para {quadra_number}')
        #             cursor.updateRow(row)
        #         else:
        #             continue
        
        # if status == 1:
        #     return True
        # else:
        #     return False
        return True

    except:
        return False

def check_lote(
    lote_features: os.PathLike,
    quadra_features: os.PathLike,
    numero_reurb_coletivo: str,
    quadra: int,
    lote: str
) -> bool:
    """
    Função para verificar se o lote existe no banco de dados.

    -----
    Args:
        lote_features(os.PathLike):
            Caminho para o shapefile do lote.
        quadra_features(os.PathLike):
            Caminho para o shapefile da quadra.
        numero_reurb_coletivo(str):
            Número do REURB coletivo.
        quadra(int):
            Número da quadra.
        lote(str):
            Número do lote.

    -----
    Returns:
        bool:
            True se o lote existe, False caso contrário.
    """
    status_quadra = check_quadra(
        lotes_features=lote_features,
        quadra_features=quadra_features,
        numero_reurb_coletivo=numero_reurb_coletivo,
        quadra=quadra
    )

    lote = arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=lote_features,
        selection_type='NEW_SELECTION',
        where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\' AND quadra = {quadra} AND lote = \'{lote}\''
    )

    with arcpy.da.SearchCursor(lote, ['validado']) as cursor:
        for row in cursor:
            status = row[0]

    #lote não existe na quadra
    if int(lote[1]) == 0 or status_quadra is False:
        #quadra não existe
        if status_quadra is False:
            arcpy.AddError(status_quadra)
            arcpy.AddError('Quadra não existe')
            return False
        else:
            arcpy.AddError('Lote não existe na quadra')
            return False
    #lote em andamento
    # Code	Description
    # P: Pendente
    # V: Validado
    # NV: Não validado
    elif status != 'V':
        # print(dict_status_quadra[status] != dict_status_quadra[1], 'Quadra em andamento')
        arcpy.AddError('Lote em andamento')
        return False
    else:
        # print(lote[1], 'Lote encontrado na quadra')
        return True
    # if int(lote[1]) == 0 and status_quadra is False:
    #     return False
    # else:
    #     return True