# -*- coding: utf-8 -*-

import os
import arcpy

from gerar_planta import converter_base64


def formatar_json_saida(
    numero_reurb_coletivo: str,
    json_saida: dict,
    pdf_planta: os.PathLike,
    zip_lote: os.PathLike,
    area_bairro: float,
    perimetro_bairro: float,
    municipios: list,
    bairro: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    pronto: bool,
) -> dict:
    """
    Formata o JSON de saída simplificado da planta de loteamento.
    """
    json_saida['identificacaoPlanilha']['numeroProcessoColetivo'] = numero_reurb_coletivo
    json_saida['identificacaoPlanilha']['bairro'] = bairro
    json_saida['identificacaoPlanilha']['imagemPlanta'] = converter_base64(pdf_planta)
    json_saida['identificacaoPlanilha']['zipShapePlanta'] = converter_base64(zip_lote)
    json_saida['identificacaoPlanilha']['areaTotal'] = area_bairro
    json_saida['identificacaoPlanilha']['perimetroTotal'] = perimetro_bairro
    json_saida['identificacaoPlanilha']['municipiosId'] = [
        municipio['id'] for municipio in municipios
    ]
    json_saida['identificacaoPlanilha']['municipios'] = [
        municipio['nome'] for municipio in municipios
    ]
    json_saida['identificacaoPlanilha']['responsavelTecnico']['codigoCredenciamento'] = n_crea_cau
    json_saida['identificacaoPlanilha']['responsavelTecnico']['formacao'] = funcao
    json_saida['identificacaoPlanilha']['responsavelTecnico']['nome'] = responsavel_tecnico
    json_saida['pronto'] = pronto

    return json_saida
