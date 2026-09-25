# -*- coding: utf-8 -*-

import os
import arcpy

def check_status(
    feicao_bairro: os.PathLike,
    numero_reurb_coletivo: str
) -> bool:
    """
    Função para verificar se o bairro está pronto.

    -----
    Args:
        feicao_bairro(os.PathLike):
            Caminho para a camada das feições do bairro.
        numero_reurb_coletivo(str):
            Número do REURB coletivo.

    -----
    Returns:
        bool:
            True se o bairro está pronto, False caso contrário.
    """
    nome_dominio = 'status_nucleo'

    bairro = arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=feicao_bairro,
        selection_type='NEW_SELECTION',
        where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\''
    )

    with arcpy.da.SearchCursor(bairro, ['status']) as cursor:
        for row in cursor:
            status = row[0]

    # status do bairro
    # bairro em andamento
    # Code	Description
    # 4: Vetorização concluída
    if status != 4:
        arcpy.AddError('Vetorização do loteamento não concluída')
        return False
    else:
        return True