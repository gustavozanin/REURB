# -*- coding: utf-8 -*-

import os
import base64
import arcpy
from arcpy import _mp
from arcpy.cim import CIMNumericFormat
from typing import Literal

from caminhos_gerais import projeto_arcgis, layout_mapa
from caminho_simbologias import (
    simbologia_lote,
    simbologia_confrontantes,
    simbologia_vertices,
    simbologia_lote_overview,
    simbologia_quadra_overview
)

def __adicionar_camada(
    aprx_map: _mp.MapFrame,
    feature: os.PathLike,
    simbologia: os.PathLike
) -> None:
    """
    Adiciona uma camada ao map frame ou overview
    """
    arcpy.AddMessage(f'Adicionando a camada: {feature}')
    
    # Verificar se a simbologia existe antes de usar
    if simbologia and not os.path.exists(simbologia):
        arcpy.AddWarning(f'⚠ Arquivo de simbologia não encontrado: {simbologia}')
        # Continua sem aplicar simbologia
    
    if int(arcpy.management.GetCount(feature)[0]):
        layer = aprx_map.addDataFromPath(feature)
        
        # Só aplica simbologia se o arquivo existir
        if simbologia and os.path.exists(simbologia):
            try:
                arcpy.ApplySymbologyFromLayer_management(
                    in_layer=layer,
                    in_symbology_layer=simbologia,
                    symbology_fields=None,
                    update_symbology='DEFAULT'
                )
            except Exception as e:
                arcpy.AddWarning(f'⚠ Erro ao aplicar simbologia: {str(e)}')
        else:
            arcpy.AddMessage(f'⚠ Simbologia não aplicada (arquivo não encontrado)')
    
    arcpy.AddMessage(f'Camada adicionada: {feature}')

def __ajustar_escala_visualizacao(
    aprx_map: _mp.MapFrame,
    layout_planta: _mp.Layout,
    feature_extend: os.PathLike,
    element_wildcard: Literal['MAP_FRAME', 'OVERVIEW_MAP_FRAME'] = None
) -> None:
    """
    Ajusta a escala de visualização do mapa

    -----
    Args:
        aprx_map(arcpy.mp.Map):
            Map frame ou overview
        feature_extend(os.PathLike):
            Camada a ser ajustada
        element_wildcard(Literal):
            Wildcard para o elemento do mapa

    -----
    Returns:
        None
    """
    arcpy.AddMessage(f'Ajustando a escala de visualização do mapa')
    extent = arcpy.Describe(
        value=feature_extend
    ).extent
    map_frame_planta = layout_planta.listElements(
        element_type="MAPFRAME_ELEMENT",
        wildcard=element_wildcard
    )[0]
    map_frame_planta.map = aprx_map
    map_frame_planta.camera.setExtent(extent)
    aprx_map.defaultCamera = map_frame_planta.camera
    map_scale = map_frame_planta.camera.scale

    map_scale_rounded_up = map_scale*1.2
    map_scale_rounded_up = ((((map_scale_rounded_up) // 50) + 1 ) * 50)
    arcpy.AddMessage(f'A escala de visualização do mapa ajustada para {map_scale_rounded_up}')
    map_frame_planta.camera.scale = map_scale_rounded_up
    extent_map_frame = map_frame_planta.camera.getExtent()
    map_frame_planta.camera.setExtent(extent_map_frame)
    arcpy.AddMessage(f'A escala de visualização do mapa ajustada')

def __ajustar_textos_layout(
    layout_planta: _mp.Layout,
    interessado: str,
    interessado_cpf: str,
    bairro: str,
    municipio: str,
    logradouro: str,
    quadra: str,
    lote: str,
    area: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    banda: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
) -> None:
    """
    Ajusta os textos do layout
    
    -------
    Args:
        layout_planta: _mp.Layout
            Layout da planta.
        interessado: str
            Nome do interessado.
        interessado_cpf: str
            CPF do interessado.
        bairro: str
            Bairro do interessado.
        municipio: str
            Município do interessado.
        denominacao: str
            Denominação do lote.
        quadra: str
            Número da quadra.
        lote: str
            Número do lote.
        area: str
            Área do lote.
        perimetro: str
            Perímetro do lote.
        data: str
            Data da geração da planta.
        fusoutm: str
            Fuso UTM do lote.
        responsavel_tecnico: str
            Nome do responsável técnico.
        funcao: str
            Função do responsável técnico.
        n_crea_cau: str
            Número de CREA/CAU do responsável técnico.

    -------
    Returns:
        None
    """
    dict_alteracoes_textos = {
        '{interessado}': interessado,
        '{interessado_cpf}': interessado_cpf,
        '{bairro}': bairro,
        '{municipio}': municipio,
        '{denominacao}': logradouro,
        '{quadra}': quadra,
        '{lote}': lote,
        '{area}': area,
        '{perimetro}': perimetro,
        '{data}': data,
        '{fusoutm}': fusoutm,
        '{responsavel_tecnico}': responsavel_tecnico,
        '{funcao}': funcao,
        '{n_crea_cau}': n_crea_cau,
    }

    for elemento, valor in dict_alteracoes_textos.items():
        texto_layout = layout_planta.listElements(
            element_type="TEXT_ELEMENT",
            wildcard=f'{elemento}'
        )[0]
        arcpy.AddMessage(f'Ajustando o texto {texto_layout.text} do layout')
        texto_layout.text = valor
        arcpy.AddMessage(f'O texto {elemento} ajustado para {valor}')

    return layout_planta

def __ajustar_tabela_dados(
    layout_planta: _mp.Layout
) -> _mp.Layout:
    """
    Ajusta a tabela com dados limitrofes
    
    -------
    Args:
        layout_planta(layout_planta):
            Layout da planta.

    -------
    Returns:
        _mp.Layout:
            Layout da planta ajustado.
    """
    dict_fields = {
        'de': 'De',
        'para': 'Para',
        'azimute': 'Azimute',
        'distancia': 'Distância',
        'E': 'E (x)',
        'N': 'N (y)'
    }
    map_frame = layout_planta.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard='MAP_FRAME'
    )[0]

    lyr = map_frame.map.listLayers('confrontantes_lote_final')[0]
    print(lyr.name)
    # print(lyrs)
    # for lyr in lyrs:
    #     print(lyr.name)    

    tabela = layout_planta.listElements(
        element_type='TABLEFRAME_ELEMENT',
        wildcard='tabela_dados'
    )[0]

    tabela.table = lyr

    tabela.fields = list(dict_fields.keys())
    # tabela.fields.displayName = list(dict_fields.values())

    tabela.setAnchor('CENTER_POINT')

    cim_tabela = tabela.getDefinition('V3')

    # Configurar nomes de exibição e centralizar valores
    for field in cim_tabela.fields:

        # Para campos de texto, centralizar via textSymbol
        if hasattr(field, 'textSymbol') and field.textSymbol is not None:
            try:
                if hasattr(field.textSymbol, 'symbol'):
                    if hasattr(field.textSymbol.symbol, 'horizontalAlignment'):
                        field.textSymbol.symbol.horizontalAlignment = 'Center'
            except:
                pass
        
        # Centralizar também o cabeçalho
        if hasattr(field, 'headingTextSymbol') and field.headingTextSymbol is not None:
            try:
                if hasattr(field.headingTextSymbol, 'symbol'):
                    if hasattr(field.headingTextSymbol.symbol, 'horizontalAlignment'):
                        field.headingTextSymbol.symbol.horizontalAlignment = 'Center'
            except:
                pass

    tabela.setDefinition(cim_tabela)

    return layout_planta

def exportar_planta_para_pdf(
    layout_planta: _mp.Layout,
    numero_reurb_coletivo: str,
    quadra: int,
    lote: int
) -> os.PathLike:
    """
    Exporta a planta para PDF
    
    -------
    Args:
        layout_planta: _mp.Layout
            Layout da planta.
        numero_reurb_coletivo: str
            Número do REURB coletivo.
        quadra: int
            Número da quadra.
        lote: int
            Número do lote.

    -------
    Returns:
        os.PathLike:
            Caminho para o PDF da planta.
    """
    arcpy.AddMessage(f'Exportando a planta para PDF')
    pdf_path = os.path.join(
        arcpy.env.scratchFolder,
        f'planta_{numero_reurb_coletivo.replace("/", "_")}_{quadra}_{lote}.pdf'
    )
    layout_planta.exportToPDF(
        out_pdf=pdf_path
    )
    arcpy.AddMessage(f'Planta exportada para PDF')

    return pdf_path

def converter_base64(
    file: os.PathLike
) -> str:
    """
    Converte um arquivo para base64
    
    -------
    Args:
        file: os.PathLike
            Caminho para o arquivo.

    -------
    Returns:
        str:
            String em base64.
    """
    encoded_string=""
    arcpy.AddMessage(f'Convertendo o arquivo para base64')
    with open(file, "rb") as _file:
        encoded_string = str(base64.b64encode(_file.read()), "UTF8")
    arcpy.AddMessage(f'Arquivo convertido para base64')
    
    return encoded_string

def gerar_planta(
    lote_selecionado: os.PathLike,
    confrontantes_lote: os.PathLike,
    vertices_lote: os.PathLike,
    lotes_layout: os.PathLike,
    interessado: str,
    interessado_cpf: str,
    bairro: str,
    municipio: str,
    logradouro: str,
    quadra: str,
    lote: str,
    area: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    banda: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str
) -> _mp.Layout:
    """
    Gera a planta
    
    -------
    Args:
        lote_selecionado: os.PathLike
            Caminho para o shapefile do lote selecionado.
        confrontantes_lote: os.PathLike
            Caminho para o shapefile dos confrontantes do lote.
        vertices_lote: os.PathLike
            Caminho para o shapefile dos vértices do lote.
        lotes_layout: os.PathLike
            Caminho para o shapefile dos lotes layout.
        interessado: str
            Nome do interessado.
        interessado_cpf: str
            CPF do interessado.
        bairro: str
            Bairro do interessado.
        municipio: str
            Município do interessado.
        logradouro: str
            Logradouro do endereço do lote.
        quadra: str
            Número da quadra.
        lote: str
            Número do lote.
        area: str
            Área do lote.
        perimetro: str
            Perímetro do lote.
        data: str
            Data da geração da planta.
        fusoutm: str
            Fuso UTM do lote.
        responsavel_tecnico: str
            Nome do responsável técnico.
        funcao: str
            Função do responsável técnico.
        n_crea_cau: str
            Número de CREA/CAU do responsável técnico.

    -------
    Returns:
        _mp.Layout:
            Layout da planta.
    """
    aprx = arcpy.mp.ArcGISProject(
        aprx_path=projeto_arcgis
    )

    map_frame_planta = aprx.listMaps()[0]
    map_overview_planta = aprx.listMaps()[1]
    layout_planta = aprx.listLayouts()[0]

    #Adicionando o lote selecionado ao map frame
    camadas_map_frame = {
        lote_selecionado: simbologia_lote,
        confrontantes_lote: simbologia_confrontantes,
        vertices_lote: simbologia_vertices
    }

    for camada, simbologia in camadas_map_frame.items():
        __adicionar_camada(
            aprx_map=map_frame_planta,
            feature=camada,
            simbologia=simbologia
        )

    #Adicionar camadas ao overview
    camadas_overview = {
        lote_selecionado: simbologia_lote_overview,
        lotes_layout: simbologia_quadra_overview
    }

    for camada, simbologia in camadas_overview.items():
        __adicionar_camada(
            aprx_map=map_overview_planta,
            feature=camada,
            simbologia=simbologia
        )

    #Ajustar escala de visualização do map frame e overview
    #map_frame
    __ajustar_escala_visualizacao(
        aprx_map=map_frame_planta,
        layout_planta=layout_planta,
        feature_extend=lote_selecionado,
        element_wildcard='MAP_FRAME'
    )

    #overview
    __ajustar_escala_visualizacao(
        aprx_map=map_overview_planta,
        layout_planta=layout_planta,
        feature_extend=lotes_layout,
        element_wildcard='OVERVIEW_MAP_FRAME'
    )

    #Ajustar textos do layout
    layout_planta = __ajustar_textos_layout(
        layout_planta=layout_planta,
        interessado=interessado,
        interessado_cpf=interessado_cpf,
        bairro=bairro,
        municipio=municipio,
        logradouro=logradouro,
        quadra=quadra,
        lote=lote,
        area=area,
        perimetro=perimetro,
        data=data,
        fusoutm=fusoutm,
        banda=banda,
        responsavel_tecnico=responsavel_tecnico,
        funcao=funcao,
        n_crea_cau=n_crea_cau,
    )

    #ajustar tabela com dados limitrofes
    layout_planta = __ajustar_tabela_dados(
        layout_planta=layout_planta
    )

    return layout_planta