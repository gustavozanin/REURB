# -*- coding: utf-8 -*-

import os
import arcpy

def check_reurb_coletivo(
    feicao_bairro: os.PathLike,
    numero_reurb_coletivo: str
) -> bool:
    """
    Verifica se o número do REURB coletivo existe.
    """
    select_reurb_coletivo = arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=feicao_bairro,
        selection_type='NEW_SELECTION',
        where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\''
    )

    if int(select_reurb_coletivo[1]) == 0:
        arcpy.AddError('Número de REURB coletivo inexistente')
        return False
    else:
        return True