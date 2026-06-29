# -*- coding: utf-8 -*-

import os
import arcpy

def check_responsavel_tecnico(
    lote_features: os.PathLike,
    numero_reurb_coletivo: str,
    quadra: int,
    lote: str,
    responsavel_tecnico_tabela: os.PathLike
) -> tuple[bool, str, str, str]:
    """
    Verifica se o responsável técnico existe no banco de dados.

    -------
    Args:
        lote_features(os.PathLike):
            Caminho para o shapefile do lote.
        numero_reurb_coletivo(str):
            Número do REURB coletivo.
        quadra(int):
            Número da quadra.
        lote(str):
            Número do lote.
        responsavel_tecnico_tabela(os.PathLike):
            Caminho para a tabela de responsáveis técnicos.

    -------
    Returns:
        tuple[bool, str, str, str]:
            Tupla contendo se o responsável técnico existe, o nome do responsável técnico, a formação e o código de credenciamento.
    """
    with arcpy.da.SearchCursor(lote_features, ['responsavel_tecnico'], where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\' AND quadra = {quadra} AND lote = \'{lote}\'') as search_cursor:
        for row in search_cursor:
            responsavel_tecnico = row[0]

    with arcpy.da.SearchCursor(responsavel_tecnico_tabela, ['nome', 'formacao', 'credenciamento'], where_clause=f'nome = \'{responsavel_tecnico}\'') as search_cursor:
        for row in search_cursor:
            if row[0] == responsavel_tecnico:
                formacao = row[1]
                codigo_credenciamento = row[2]
                break

    if responsavel_tecnico is None:
        arcpy.AddError(f'Responsável técnico não preenchido')
        return False, responsavel_tecnico, None, None
    elif formacao is None or codigo_credenciamento is None:
        arcpy.AddError(f'Preenchimento divergente ou responsável técnico não cadastrado')
        return False, responsavel_tecnico, None, None
    else:
        return True, responsavel_tecnico, formacao, codigo_credenciamento
