# -*- coding: utf-8 -*-

import arcpy


def _campo_existe(camada, nome_campo: str) -> bool:
    campos = {campo.name.lower() for campo in arcpy.ListFields(camada)}
    return nome_campo.lower() in campos


def check_quadras_lotes(quadras_layer, lotes_layer, lote_camada) -> bool:
    """
    Verifica existência de quadras e lotes e presença do campo created_user.

    Args:
        quadras_layer: Feature layer de quadras filtrado por n_coletivo.
        lotes_layer: Feature layer de lotes filtrado por n_coletivo.
        lote_camada: Caminho da feature class de lotes (para validar campos).

    Returns:
        True se todas as verificações passarem; False caso contrário.
    """
    contagem_quadras = int(arcpy.GetCount_management(in_rows=quadras_layer)[0])
    if contagem_quadras == 0:
        arcpy.AddError('Não há quadras para o núcleo informado')
        return False

    contagem_lotes = int(arcpy.GetCount_management(in_rows=lotes_layer)[0])
    if contagem_lotes == 0:
        arcpy.AddError('Não há lotes para o núcleo informado')
        return False

    if not _campo_existe(lote_camada, 'created_user'):
        arcpy.AddError(
            "Campo 'created_user' ausente na camada de lotes. "
            'Habilite o editor tracking na camada de produção.'
        )
        return False

    return True
