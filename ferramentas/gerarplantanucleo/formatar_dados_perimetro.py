# -*- coding: utf-8 -*-

import os
import arcpy
from normalizacao import arredondar_4

def formatar_dados_perimetro(
    confrontantes_bairro: os.PathLike
) -> list:
    """
    Formata os dados de perimetro
    
    -------
    Args:
        confrontantes_bairro: os.PathLike
            Caminho para a camada de confrontantes do bairro.
    
    -------
    Returns:
        list:
            Lista de dados de perimetro formatados.
    """
    dados_perimetro = []
    with arcpy.da.SearchCursor(confrontantes_bairro, ['de', 'para', 'azimute', 'distancia', 'confrontantes', 'E', 'N']) as cursor:
        for row in cursor:
            de = row[0]
            para = row[1]
            azimute = row[2]
            distancia = row[3]
            confrontantes = row[4]
            E = row[5]
            N = row[6]

            dados_perimetro.append(
                {
                    'vertice': de,
                    'confrontante': confrontantes,
                    'azimute': azimute,
                    'distancia': arredondar_4(distancia),
                    'eLong': arredondar_4(E),
                    'nLat': arredondar_4(N)
                }
            )

    return dados_perimetro
