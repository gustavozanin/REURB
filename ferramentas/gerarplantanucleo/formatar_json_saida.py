# -*- coding: utf-8 -*-

import os
import json
import arcpy
import base64

from gerar_planta import converter_base64
from normalizacao import arredondar_4


def arquivo_base64(caminho):
    if not caminho or not os.path.exists(caminho):
        return ''
    with open(caminho, 'rb') as arquivo:
        return base64.b64encode(arquivo.read()).decode('utf-8')


def nome_arquivo(caminho):
    return os.path.basename(caminho) if caminho else ''


def formatar_json_saida(
    numero_reurb_coletivo: str,
    json_entrada: dict,
    json_saida: dict,
    dados_perimetro: list,
    dados_perimetro_planta_simplificada: list,
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
    pdf_planta_simplificada_com_quadro: os.PathLike = None,
    pdf_quadro_coordenadas: os.PathLike = None,
    pdf_planta_vertices_memorial_com_memorial: os.PathLike = None,
    pdf_memorial_descritivo: os.PathLike = None,
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
    json_saida['identificacaoPlanilha']['bairro'] = json_entrada['dados']['bairro']
    json_saida['identificacaoPlanilha']['imagemPlanta'] = converter_base64(pdf_planta)
    json_saida['identificacaoPlanilha']['imagemPlantaSimplificadaComQuadro'] = arquivo_base64(
        pdf_planta_simplificada_com_quadro or pdf_planta
    )
    json_saida['identificacaoPlanilha']['imagemPlantaVerticesMemorialComMemorial'] = arquivo_base64(
        pdf_planta_vertices_memorial_com_memorial
    )
    json_saida['identificacaoPlanilha']['memorialDescritivo'] = arquivo_base64(pdf_memorial_descritivo)
    json_saida['identificacaoPlanilha']['quadroCoordenadasPlantaSimplificada'] = arquivo_base64(pdf_quadro_coordenadas)
    json_saida['identificacaoPlanilha']['fluxoDocumentos'] = {
        'plantaSimplificada': {
            'tipo': 'planta_simplificada_com_quadro_coordenadas',
            'arquivo': nome_arquivo(pdf_planta_simplificada_com_quadro or pdf_planta),
            'anexo': nome_arquivo(pdf_quadro_coordenadas),
            'usaVertices': 'dadosPerimetroPlantaSimplificada',
            'descricao': 'Planta grafica simplificada para legibilidade, anexada ao Quadro de Coordenadas da Planta Simplificada.'
        },
        'plantaVerticesMemorial': {
            'tipo': 'planta_vertices_memorial_com_memorial_descritivo',
            'arquivo': nome_arquivo(pdf_planta_vertices_memorial_com_memorial),
            'anexo': nome_arquivo(pdf_memorial_descritivo),
            'usaVertices': 'dadosPerimetro',
            'descricao': 'Planta de conferencia com a sequencia integral de vertices, anexada ao Memorial Descritivo.'
        },
        'referenciaAreaPerimetro': 'Area e perimetro impressos correspondem ao perimetro real/completo, descrito no Memorial Descritivo.'
    }
    json_saida['identificacaoPlanilha']['zipShapePlanta'] = converter_base64(zip_lote)
    json_saida['identificacaoPlanilha']['areaTotal'] = arredondar_4(area_bairro)
    json_saida['identificacaoPlanilha']['perimetroTotal'] = arredondar_4(perimetro_bairro)
    json_saida['identificacaoPlanilha']['municipiosId'] = [municipio['id'] for municipio in municipios]
    json_saida['identificacaoPlanilha']['municipios'] = [municipio['nome'] for municipio in municipios]
    
    #perimetros
    json_saida['identificacaoPlanilha']['perimetros'][0]['areaPerimetro'] = arredondar_4(area_bairro)
    json_saida['identificacaoPlanilha']['perimetros'][0]['fusoUTM'] = fusoutm
    json_saida['identificacaoPlanilha']['perimetros'][0]['hemisferio'] = fusoutm[-1]
    json_saida['identificacaoPlanilha']['perimetros'][0]['idMunicipio'] = municipios_principal['id']
    json_saida['identificacaoPlanilha']['perimetros'][0]['idMunicipioLista'] = [municipio['id'] for municipio in municipios]
    json_saida['identificacaoPlanilha']['perimetros'][0]['idMunicipioPrincipal'] = municipios_principal['id']
    json_saida['identificacaoPlanilha']['perimetros'][0]['municipio'] = municipios_principal['nome']
    json_saida['identificacaoPlanilha']['perimetros'][0]['meridianoCentral'] = arredondar_4(meridiano_central)
    json_saida['identificacaoPlanilha']['perimetros'][0]['banda'] = banda
    json_saida['identificacaoPlanilha']['perimetros'][0]['dadosPerimetro'] = dados_perimetro
    json_saida['identificacaoPlanilha']['perimetros'][0]['dadosPerimetroPlantaSimplificada'] = (
        dados_perimetro_planta_simplificada or dados_perimetro
    )

    #responsavelTecnico
    json_saida['identificacaoPlanilha']['responsavelTecnico']['codigoCredenciamento'] = n_crea_cau
    json_saida['identificacaoPlanilha']['responsavelTecnico']['formacao'] = funcao
    json_saida['identificacaoPlanilha']['responsavelTecnico']['nome'] = responsavel_tecnico

    #pronto
    json_saida['pronto'] = pronto

    return json_saida
