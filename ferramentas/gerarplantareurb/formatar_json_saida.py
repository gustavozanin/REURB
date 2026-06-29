# -*- coding: utf-8 -*-

import os
import json
import arcpy

from gerar_planta import converter_base64

def formatar_json_saida(
    json_entrada: dict,
    json_saida: dict,
    dados_perimetro: list,
    pdf_planta: os.PathLike,
    zip_lote: os.PathLike,
    area_lote: float,
    perimetro_lote: float,
    municipios: list,
    municipios_principal: dict,
    logradouro: str,
    denominacao: str,
    n_predial: int,
    bairro: str,
    fusoutm: str,
    banda: str,
    meridiano_central: float,
    responsavel_tecnico: str,
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
    json_saida['identificacaoPlanilha']['areaLiquida'] = area_lote
    json_saida['identificacaoPlanilha']['areaTotal'] = area_lote
    json_saida['identificacaoPlanilha']['areadeduzida'] = 0
    json_saida['identificacaoPlanilha']['imagemPlanta'] = converter_base64(pdf_planta)
    json_saida['identificacaoPlanilha']['zipShapePlanta'] = converter_base64(zip_lote)
    json_saida['identificacaoPlanilha']['perimetroTotal'] = perimetro_lote
    json_saida['identificacaoPlanilha']['municipiosId'] = [municipio['id'] for municipio in municipios]
    json_saida['identificacaoPlanilha']['municipios'] = [municipio['nome'] for municipio in municipios]

    #informacoesInteressado
    json_saida['identificacaoPlanilha']['informacoesInteressado']['bairro'] = bairro
    json_saida['identificacaoPlanilha']['informacoesInteressado']['cpf'] = json_entrada['identificacaoPlanilha']['cpfCnpj']
    json_saida['identificacaoPlanilha']['informacoesInteressado']['endereco'] = logradouro
    json_saida['identificacaoPlanilha']['informacoesInteressado']['lote'] = json_entrada['identificacaoPlanilha']['lote']
    json_saida['identificacaoPlanilha']['informacoesInteressado']['numero'] = json_entrada['identificacaoPlanilha']['lote']
    json_saida['identificacaoPlanilha']['informacoesInteressado']['quadra'] = json_entrada['identificacaoPlanilha']['quadra']
    
    #perimetros
    json_saida['identificacaoPlanilha']['perimetros'][0]['denominacao'] = denominacao
    json_saida['identificacaoPlanilha']['perimetros'][0]['areaPerimetro'] = area_lote
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

    # with open(os.path.join(arcpy.env.scratchFolder,'json_saida.json'), 'w', encoding='utf-8') as f:
    #     json.dump(json_saida, f, ensure_ascii=False)

    return json_saida
