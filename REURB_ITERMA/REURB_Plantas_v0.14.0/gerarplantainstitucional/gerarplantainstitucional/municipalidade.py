# -*- coding: utf-8 -*-

import arcpy
import os
from tabulando_intersecao import tabulacao_intersecao

def municipalidade(
        feicao_perimetro: os.PathLike,
        municipios: os.PathLike,
        area:float
) -> tuple[list, dict]:
    """
    Responsável por selecionar o municipio de acordo com o bairro.

    -------
    Args:
        feicao_perimetro(os.PathLike):
            Caminho para a camada que contém o perímetro a ser analisado no processo de regularização fundiária.
        municipios(os.PathLike):
            Caminho para a camada que contém os municipios.
        area(float):
            Valor de área para o perímetro avaliado no processo.

    -------
    Returns:
        list:
            Tupla contendo a lista de municipios selecionados e o municipio principal.
    """
    class_fields = [
        'CD_MUN',
        'NM_MUN'
    ]

    intercecao_mun = tabulacao_intersecao(
        feicao_perimetro=feicao_perimetro,
        intersecao_dissolvida=municipios,
        class_fields=class_fields,
        area=area
    )

    list_municipalidade = list()

    dict_municipalidade = {
        'id': '',
        'nome': ''
    }
    municipio_principal = {
        'id': '',
        'nome': ''
    }

    with arcpy.da.SearchCursor(intercecao_mun, class_fields + ['porcentagem']) as cursor:
        maior_porcentagem = 0
        for row in cursor:
            CD_MUN = row[0]
            NM_MUN = row[1]
            percentual = 10
            if row[-1] > percentual:
                if CD_MUN not in dict_municipalidade['id']:
                    # percentual = row[-1]
                    dict_municipalidade['id'] = CD_MUN
                    dict_municipalidade['nome'] = NM_MUN
                    list_municipalidade.append(dict_municipalidade)
                #pegar municipio com maior porcentagem
                if row[-1] > maior_porcentagem:
                    maior_porcentagem = row[-1]
                    municipio_principal['id'] = row[0]
                    municipio_principal['nome'] = row[1]
    
    return list_municipalidade, municipio_principal