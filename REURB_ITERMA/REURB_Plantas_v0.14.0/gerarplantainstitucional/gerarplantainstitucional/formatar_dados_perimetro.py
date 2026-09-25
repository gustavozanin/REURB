# -*- coding: utf-8 -*-

import os
import arcpy


def _ordem_vertice(codigo):
    """Número do vértice P-n para ordenar o anel do memorial."""
    try:
        return int(str(codigo or '').split('-')[-1])
    except (TypeError, ValueError):
        return 0


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
                    'vertice_para': para,
                    'confrontante': confrontantes,
                    'azimute': azimute,
                    'distancia': distancia,
                    'eLong': E,
                    'nLat': N
                }
            )

    # Garante P-n → P-n+1 na ordem do anel; o SearchCursor não ordena.
    dados_perimetro.sort(
        key=lambda item: (
            _ordem_vertice(item.get('vertice')),
            str(item.get('vertice') or ''),
        )
    )
    return dados_perimetro