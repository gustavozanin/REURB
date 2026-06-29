# -*- coding: utf-8 -*-

import os
import arcpy

def formatar_dados_perimetro(
    confrontantes_lote: os.PathLike,
    json_dados_perimetro: os.PathLike
) -> list:
    """
    Formata os dados de perimetro
    
    -------
    Args:
        confrontantes_lote: os.PathLike
            Caminho para o shapefile de confrontantes do lote.
        json_dados_perimetro: os.PathLike
            Caminho para o json de dados de perimetro.
    
    -------
    Returns:
        list:
            Lista de dados de perimetro formatados.
    """
    dados_perimetro = []
    with arcpy.da.SearchCursor(confrontantes_lote, ['de', 'para', 'azimute', 'distancia', 'confrontantes', 'E', 'N']) as cursor:
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
                    'distancia': distancia,
                    'eLong': E,
                    'nLat': N
                }
            )

    return dados_perimetro