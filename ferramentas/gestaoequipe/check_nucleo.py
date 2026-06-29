# -*- coding: utf-8 -*-

import arcpy


def check_nucleo(nucleo_layer) -> bool:
    """
    Verifica se existe exatamente um perímetro de núcleo selecionado.

    Args:
        nucleo_layer: Feature layer de bairro já filtrado por n_coletivo.

    Returns:
        True se houver exatamente um registro; False caso contrário.
    """
    contagem = int(
        arcpy.GetCount_management(
            in_rows=nucleo_layer
        )[0]
    )

    if contagem == 0:
        arcpy.AddError('Núcleo inexistente para o número de processo coletivo informado')
        return False

    if contagem > 1:
        arcpy.AddError(
            f'Foram encontrados {contagem} perímetros de núcleo para o mesmo '
            'número de processo coletivo. Corrija a ambiguidade no banco de dados.'
        )
        return False

    return True
