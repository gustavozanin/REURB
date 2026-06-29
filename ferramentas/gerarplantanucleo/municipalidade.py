# -*- coding: utf-8 -*-

import os

import arcpy

from tabulando_intersecao import tabulacao_intersecao


MUNICIPIO_PADRAO = {'id': '', 'nome': 'Peri Mirim'}


def municipalidade(
        feicao_perimetro: os.PathLike,
        municipios: os.PathLike,
        area: float
) -> tuple[list, dict]:
    if not municipios or not arcpy.Exists(municipios):
        arcpy.AddWarning(
            f"Camada de municipios nao encontrada ou invalida: {municipios}. "
            "A execucao continuara usando Peri Mirim."
        )
        return [MUNICIPIO_PADRAO.copy()], MUNICIPIO_PADRAO.copy()

    campos_municipios = {field.name.upper(): field.name for field in arcpy.ListFields(municipios)}
    if 'CD_MUN' in campos_municipios and 'NM_MUN' in campos_municipios:
        class_fields = [
            campos_municipios['CD_MUN'],
            campos_municipios['NM_MUN']
        ]
    elif 'GEOCODIGO' in campos_municipios and 'NOME' in campos_municipios:
        class_fields = [
            campos_municipios['GEOCODIGO'],
            campos_municipios['NOME']
        ]
    else:
        arcpy.AddWarning(
            "Camada de municipios sem campos reconhecidos de codigo/nome. "
            "A execucao continuara usando Peri Mirim."
        )
        return [MUNICIPIO_PADRAO.copy()], MUNICIPIO_PADRAO.copy()

    intercecao_mun = tabulacao_intersecao(
        feicao_perimetro=feicao_perimetro,
        intersecao_dissolvida=municipios,
        class_fields=class_fields,
        area=area
    )

    list_municipalidade = []
    municipio_principal = {
        'id': '',
        'nome': ''
    }

    maior_porcentagem = 0
    ids_adicionados = set()
    with arcpy.da.SearchCursor(intercecao_mun, class_fields + ['porcentagem']) as cursor:
        for row in cursor:
            cd_mun = row[0]
            nm_mun = row[1]
            percentual = row[-1]

            if percentual > 10 and cd_mun not in ids_adicionados:
                list_municipalidade.append({'id': cd_mun, 'nome': nm_mun})
                ids_adicionados.add(cd_mun)

            if percentual > maior_porcentagem:
                maior_porcentagem = percentual
                municipio_principal['id'] = cd_mun
                municipio_principal['nome'] = nm_mun

    if not municipio_principal['nome']:
        arcpy.AddWarning('Municipio nao identificado por intersecao. Usando Peri Mirim.')
        return [MUNICIPIO_PADRAO.copy()], MUNICIPIO_PADRAO.copy()

    return list_municipalidade, municipio_principal
