# -*- coding: utf-8 -*-

import os
import json
import arcpy

from gerar_planta import converter_base64

def formatar_json_saida(
    numero_reurb_coletivo: str,
    bairro: str,
    json_entrada: dict,
    json_saida: dict,
    dados_perimetro: list,
    pdf_planta: os.PathLike,
    zip_lote: os.PathLike,
    area_bairro: float,
    perimetro_bairro: float,
    municipios: list,
    municipios_principal: dict,
    fusoutm: str,
    banda: str,
    meridiano_central: float,
    responsavel_tecnico,
    funcao: str,
    n_crea_cau: str,
    pronto: bool,
) -> dict:
    """
    Formata o json de saida
    
    -------
    Args:
        json_entrada: dict
            Json de entrada.
        json_saida: dict
            Json de saida.
        json_dados_perimetro: dict
            Json de dados de perimetro.
        layout_planta: os.PathLike
            Caminho para o layout da planta.
        zip_lote: os.PathLike
            Caminho para o zip do lote.
    -------
    Returns:
        dict:
            Json de saida formatado.
    """

    #identificacaoPlanilha
    json_saida['identificacaoPlanilha']['numeroProcessoColetivo'] = numero_reurb_coletivo
    json_saida['identificacaoPlanilha']['bairro'] = bairro
    json_saida['identificacaoPlanilha']['imagemPlanta'] = converter_base64(pdf_planta)
    json_saida['identificacaoPlanilha']['zipShapePlanta'] = converter_base64(zip_lote)
    json_saida['identificacaoPlanilha']['areaTotal'] = area_bairro
    json_saida['identificacaoPlanilha']['perimetroTotal'] = perimetro_bairro
    json_saida['identificacaoPlanilha']['municipiosId'] = [municipio['id'] for municipio in municipios]
    json_saida['identificacaoPlanilha']['municipios'] = [municipio['nome'] for municipio in municipios]
    
    #perimetros
    json_saida['identificacaoPlanilha']['perimetros'][0]['areaPerimetro'] = area_bairro
    json_saida['identificacaoPlanilha']['perimetros'][0]['fusoUTM'] = fusoutm
    json_saida['identificacaoPlanilha']['perimetros'][0]['hemisferio'] = fusoutm[-1]
    json_saida['identificacaoPlanilha']['perimetros'][0]['idMunicipio'] = municipios_principal['id']
    json_saida['identificacaoPlanilha']['perimetros'][0]['idMunicipioLista'] = [municipio['id'] for municipio in municipios]
    json_saida['identificacaoPlanilha']['perimetros'][0]['idMunicipioPrincipal'] = municipios_principal['id']
    json_saida['identificacaoPlanilha']['perimetros'][0]['municipio'] = municipios_principal['nome']
    json_saida['identificacaoPlanilha']['perimetros'][0]['meridianoCentral'] = meridiano_central
    json_saida['identificacaoPlanilha']['perimetros'][0]['banda'] = banda
    json_saida['identificacaoPlanilha']['perimetros'][0]['dadosPerimetro'] = dados_perimetro

    #responsavelTecnico
    json_saida['identificacaoPlanilha']['responsavelTecnico']['codigoCredenciamento'] = n_crea_cau
    json_saida['identificacaoPlanilha']['responsavelTecnico']['formacao'] = funcao
    json_saida['identificacaoPlanilha']['responsavelTecnico']['nome'] = responsavel_tecnico

    #pronto
    json_saida['pronto'] = pronto

    return json_saida