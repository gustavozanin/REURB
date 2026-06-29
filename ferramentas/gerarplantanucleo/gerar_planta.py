# -*- coding: utf-8 -*-

import os
import base64
import arcpy
from arcpy import _mp
from arcpy.cim import CIMNumericFormat
from typing import Literal

from caminhos_gerais import projeto_arcgis
from caminho_simbologias import (
    simbologia_perimetro,
    simbologia_confrontantes,
    simbologia_vertices,
    simbologia_perimetro_overview
)

FONTE_QUADRO_CORPO = 3.4
FONTE_QUADRO_CABECALHO = 3.6
ALTURA_LINHA_QUADRO = 3.8
FONTE_ROTULO_CONFRONTACAO = 5.0
FONTE_ROTULO_VERTICE = 3.3

def __ajustar_tamanho_texto(simbolo, tamanho: float) -> None:
    visitados = set()

    def ajustar(objeto, profundidade=0):
        if objeto is None or profundidade > 4:
            return
        obj_id = id(objeto)
        if obj_id in visitados:
            return
        visitados.add(obj_id)

        for prop in ['size', 'fontSize', 'height', 'textSize']:
            try:
                if hasattr(objeto, prop):
                    setattr(objeto, prop, tamanho)
            except Exception:
                pass

        for prop in ['symbol', 'symbolReference', 'textSymbol']:
            try:
                if hasattr(objeto, prop):
                    ajustar(getattr(objeto, prop), profundidade + 1)
            except Exception:
                pass

        for prop in ['symbolLayers', 'layers']:
            try:
                camadas = getattr(objeto, prop, None)
                if camadas:
                    for camada in camadas:
                        ajustar(camada, profundidade + 1)
            except Exception:
                pass

    try:
        ajustar(simbolo)
    except Exception:
        pass

def __adicionar_aviso_apendice(layout_planta: _mp.Layout) -> None:
    texto = (
        "Nota: os vértices não exibidos integralmente neste quadro seguem "
        "no Apêndice - Quadro de Coordenadas Completo, anexo nas páginas seguintes."
    )
    try:
        titulares = layout_planta.listElements("TEXT_ELEMENT", "{municipio_overview}")
        if titulares:
            elemento = titulares[0]
            elemento.text = f"{texto}\nPlanta de Situacao:"
            elemento.visible = True
            try:
                simbolo = elemento.textSymbol
                __ajustar_tamanho_texto(simbolo, 5.4)
                try:
                    simbolo.symbol.color = {'RGB': [170, 0, 0, 100]}
                except Exception:
                    pass
                elemento.textSymbol = simbolo
            except Exception:
                pass
            arcpy.AddMessage('Aviso de apendice inserido no titulo da planta de situacao.')
            return

        existentes = layout_planta.listElements("TEXT_ELEMENT", "aviso_apendice_quadro")
        if existentes:
            existentes[0].text = texto
            return

        tabela = layout_planta.listElements(
            element_type='TABLEFRAME_ELEMENT',
            wildcard='tabela_dados'
        )[0]

        if hasattr(layout_planta, 'createTextElement'):
            x = tabela.elementPositionX
            y = max(tabela.elementPositionY - 0.18, 0.1)
            largura = tabela.elementWidth
            elemento = layout_planta.createTextElement(
                arcpy.Point(x, y),
                'POINT',
                texto,
                5.2,
                'Arial',
                'Regular'
            )
            elemento.name = 'aviso_apendice_quadro'
            try:
                elemento.elementWidth = largura
            except Exception:
                pass
            arcpy.AddMessage('Aviso de apêndice adicionado abaixo do quadro de coordenadas.')
        else:
            arcpy.AddWarning('Layout nao suporta createTextElement; aviso de apendice nao foi inserido.')
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel inserir aviso de apendice no layout: {str(e)}')

def __adicionar_aviso_apendice_sem_quadro(layout_planta: _mp.Layout) -> None:
    texto = (
        "Nota: o Quadro de Coordenadas e Confrontacoes completo segue "
        "no Apendice anexo nas paginas seguintes."
    )
    try:
        existentes = layout_planta.listElements("TEXT_ELEMENT", "aviso_apendice_quadro")
        if existentes:
            existentes[0].text = texto
            existentes[0].visible = True
            return

        tabela = layout_planta.listElements(
            element_type='TABLEFRAME_ELEMENT',
            wildcard='tabela_dados'
        )[0]

        if hasattr(layout_planta, 'createTextElement'):
            x = 18.0
            y = 3.1
            largura = 8.0
            try:
                x = tabela.elementPositionX
                y = tabela.elementPositionY + tabela.elementHeight / 2
                largura = tabela.elementWidth
            except Exception:
                pass
            elemento = layout_planta.createTextElement(
                arcpy.Point(x, y),
                'POINT',
                texto,
                7.0,
                'Arial',
                'Regular'
            )
            elemento.name = 'aviso_apendice_quadro'
            try:
                elemento.elementWidth = largura
            except Exception:
                pass
            arcpy.AddMessage('Aviso de apendice inserido no lugar do quadro de coordenadas.')
        else:
            arcpy.AddWarning('Layout nao suporta createTextElement; aviso de apendice nao foi inserido.')
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel inserir aviso de apendice no layout: {str(e)}')


def __forcar_aviso_apendice(layout_planta: _mp.Layout, tipo_planta='simplificada') -> None:
    if tipo_planta == 'memorial':
        texto = (
            "Observação Importante\n"
            "ATENÇÃO: esta prancha de conferência utiliza a sequência integral de vértices do Memorial Descritivo.\n"
            "A numeração dos vértices deve ser lida em conjunto com a descrição analítica completa e seus quadros de coordenadas.\n\n"
            "Planta de Situação\n"
            "Delimitação do perímetro urbano conforme vértices e coordenadas do Memorial Descritivo."
        )
    else:
        texto = (
            "Observação Importante\n"
            "ATENÇÃO: a prancha gráfica apresenta uma versão simplificada do perímetro para legibilidade.\n"
            "A descrição analítica completa, com a sequência integral de vértices e coordenadas, consta no Memorial Descritivo.\n"
            "O Quadro de Coordenadas da Planta Simplificada segue no Apêndice Anexo para conferência e assinatura.\n\n"
            "Planta de Situação\n"
            "Delimitação do perímetro urbano com vértices identificados na prancha simplificada, "
            "confrontando com vias públicas e matrículas vizinhas."
        )

    try:
        rodapes = layout_planta.listElements("TEXT_ELEMENT", "Text 1")
        if rodapes:
            elemento = rodapes[0]
            texto_base = elemento.text or ''
            if 'Observação Importante' not in texto_base:
                elemento.text = f"{texto}\n{texto_base}"
            elemento.visible = True
            try:
                simbolo = elemento.textSymbol
                __ajustar_tamanho_texto(simbolo, 4.2)
                elemento.textSymbol = simbolo
            except Exception:
                pass
            arcpy.AddMessage('Aviso de apendice inserido no rodape institucional da planta.')
            return

        existentes = layout_planta.listElements("TEXT_ELEMENT", "aviso_apendice_quadro")
        overviews = layout_planta.listElements(
            element_type='MAPFRAME_ELEMENT',
            wildcard='OVERVIEW_MAP_FRAME'
        )
        if not overviews:
            return

        overview = overviews[0]
        x = overview.elementPositionX
        y = overview.elementPositionY + overview.elementHeight + 0.08
        largura = overview.elementWidth

        if existentes:
            elemento = existentes[0]
            elemento.text = texto
            elemento.visible = True
            elemento.elementPositionX = x
            elemento.elementPositionY = y
        elif hasattr(layout_planta, 'createTextElement'):
            elemento = layout_planta.createTextElement(
                arcpy.Point(x, y),
                'POINT',
                texto,
                6.2,
                'Arial',
                'Bold'
            )
            elemento.name = 'aviso_apendice_quadro'
        else:
            return

        try:
            elemento.elementWidth = largura
        except Exception:
            pass
        try:
            simbolo = elemento.textSymbol
            __ajustar_tamanho_texto(simbolo, 6.2)
            try:
                simbolo.symbol.color = {'RGB': [180, 0, 0, 100]}
            except Exception:
                pass
            elemento.textSymbol = simbolo
        except Exception:
            pass
        arcpy.AddMessage('Aviso de apendice inserido acima da planta de situacao.')
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel criar aviso de apendice acima da planta de situacao: {str(e)}')


def __adicionar_eixo_viario_rotulos(aprx_map: _mp.MapFrame, eixo_viario: os.PathLike) -> None:
    if not eixo_viario or not arcpy.Exists(eixo_viario):
        arcpy.AddMessage('Sem rotulos de confrontantes para adicionar na planta principal.')
        return

    try:
        layer = aprx_map.addDataFromPath(eixo_viario)
        layer.name = 'Confrontacao'

        try:
            sym = layer.symbology
            if hasattr(sym, 'renderer') and hasattr(sym.renderer, 'symbol'):
                if hasattr(sym.renderer.symbol, 'color'):
                    sym.renderer.symbol.color = {'RGB': [0, 0, 0, 0]}
                if hasattr(sym.renderer.symbol, 'size'):
                    sym.renderer.symbol.size = 1
            layer.symbology = sym
        except Exception as e:
            arcpy.AddWarning(f'Nao foi possivel ocultar simbolo dos rotulos de confrontacao: {str(e)}')

        try:
            layer.showLabels = True
            for label_class in layer.listLabelClasses():
                label_class.expression = (
                    f'"<FNT size=\'{FONTE_ROTULO_CONFRONTACAO}\'>" + '
                    '$feature.label_txt + "</FNT>"'
                )
                try:
                    label_class.expressionEngine = 'Arcade'
                except Exception:
                    pass
                label_class.visible = True
        except Exception as e:
            arcpy.AddWarning(f'Nao foi possivel configurar rotulos de confrontacao: {str(e)}')

        try:
            cim_layer = layer.getDefinition('V3')
            for label_class in getattr(cim_layer, 'labelClasses', []):
                label_class.visible = True
                try:
                    label_class.expression = (
                        f'"<FNT size=\'{FONTE_ROTULO_CONFRONTACAO}\'>" + '
                        '$feature.label_txt + "</FNT>"'
                    )
                    label_class.expressionEngine = 'Arcade'
                except Exception:
                    pass
                for prop, value in [
                    ('useFormattingTags', True),
                    ('enableFormattingTags', True),
                ]:
                    try:
                        if hasattr(label_class, prop):
                            setattr(label_class, prop, value)
                    except Exception:
                        pass
                for prop, value in [
                    ('rotationExpression', '$feature.angulo'),
                    ('rotationExpressionEngine', 'Arcade'),
                    ('rotationType', 'Arithmetic'),
                ]:
                    try:
                        if hasattr(label_class, prop):
                            setattr(label_class, prop, value)
                    except Exception:
                        pass
                for prop, value in [
                    ('stackLabel', False),
                    ('allowOverrun', True),
                    ('allowOverlap', True),
                    ('placeOverlappingLabels', True),
                    ('removeDuplicateLabels', False),
                    ('neverRemove', True),
                    ('removeExtraSpaces', False),
                    ('maximumLineLength', 120),
                ]:
                    try:
                        if hasattr(label_class, prop):
                            setattr(label_class, prop, value)
                    except Exception:
                        pass
                text_symbol = getattr(label_class, 'textSymbol', None)
                if text_symbol is not None:
                    __ajustar_tamanho_texto(text_symbol, FONTE_ROTULO_CONFRONTACAO)
                    try:
                        text_symbol.symbol.color = {'RGB': [0, 0, 0, 100]}
                    except Exception:
                        pass
                placement = getattr(label_class, 'maplexLabelPlacementProperties', None)
                if placement is not None:
                    for prop, value in [
                        ('canOverrunFeature', True),
                        ('featureWeight', 'Low'),
                        ('labelBuffer', 0),
                        ('allowOverlap', True),
                        ('neverRemove', True),
                        ('rotationField', 'angulo'),
                        ('rotationType', 'Arithmetic'),
                    ]:
                        try:
                            if hasattr(placement, prop):
                                setattr(placement, prop, value)
                        except Exception:
                            pass
                standard = getattr(label_class, 'standardLabelPlacementProperties', None)
                if standard is not None:
                    for prop, value in [
                        ('labelBuffer', 0),
                        ('allowOverlap', True),
                        ('rotationField', 'angulo'),
                        ('rotationType', 'Arithmetic'),
                    ]:
                        try:
                            if hasattr(standard, prop):
                                setattr(standard, prop, value)
                        except Exception:
                            pass
            layer.setDefinition(cim_layer)
        except Exception as e:
            arcpy.AddWarning(f'Nao foi possivel ajustar rotulos de confrontacao via CIM: {str(e)}')

        arcpy.AddMessage('Rotulos resumidos de confrontacao adicionados na planta principal.')
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel adicionar rotulos de confrontacao na planta: {str(e)}')

def __reduzir_rotulos_vertices(aprx_map: _mp.MapFrame) -> None:
    try:
        camadas_vertices = [
            layer for layer in aprx_map.listLayers()
            if layer.name.lower().startswith('vertices')
        ]

        for layer in camadas_vertices:
            try:
                layer.showLabels = True
            except Exception:
                pass

            for label_class in layer.listLabelClasses():
                try:
                    label_class.expression = '$feature.rotulo'
                    label_class.visible = True
                    try:
                        label_class.name = 'Vertices'
                    except Exception:
                        pass
                except Exception:
                    pass

            try:
                cim_layer = layer.getDefinition('V3')
                for label_class in getattr(cim_layer, 'labelClasses', []):
                    label_class.visible = True
                    try:
                        label_class.expression = '$feature.rotulo'
                    except Exception:
                        pass
                    try:
                        label_class.expressionEngine = 'Arcade'
                    except Exception:
                        pass
                    text_symbol = getattr(label_class, 'textSymbol', None)
                    if text_symbol is not None:
                        __ajustar_tamanho_texto(text_symbol, FONTE_ROTULO_VERTICE)
                        try:
                            text_symbol.symbol.color = {'RGB': [0, 0, 0, 100]}
                        except Exception:
                            pass
                layer.setDefinition(cim_layer)
            except Exception:
                pass

        arcpy.AddMessage('Rotulos de vertices reativados com fonte reduzida.')
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel ajustar rotulos de vertices: {str(e)}')

def __ocultar_rotulos_confrontantes_e_logradouros(aprx_map: _mp.MapFrame) -> None:
    try:
        for layer in aprx_map.listLayers():
            nome = layer.name.lower()
            if (
                nome.startswith('confrontantes')
                or nome.startswith('logradouro')
                or 'eixo' in nome
            ):
                try:
                    layer.showLabels = False
                    for label_class in layer.listLabelClasses():
                        label_class.visible = False
                except Exception:
                    pass
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel ocultar rotulos de confrontantes/logradouros: {str(e)}')

def __limpar_rotulos_mapa_principal(aprx_map: _mp.MapFrame) -> None:
    __ocultar_rotulos_confrontantes_e_logradouros(aprx_map)

def __limpar_rotulos_mapa_principal_obsoleto(aprx_map: _mp.MapFrame) -> None:
    try:
        for layer in aprx_map.listLayers():
            nome = layer.name.lower()
            if (
                nome.startswith('confrontantes')
                or nome.startswith('logradouro')
                or 'eixo' in nome
            ):
                try:
                    layer.showLabels = False
                    for label_class in layer.listLabelClasses():
                        label_class.visible = False
                except Exception:
                    pass
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel limpar rotulos do mapa principal: {str(e)}')

def __desativado_reduzir_rotulos_vertices_antigo(aprx_map: _mp.MapFrame) -> None:
    try:
        camadas_vertices = [
            layer for layer in aprx_map.listLayers()
            if layer.name.lower().startswith('vertices')
        ]

        for layer in camadas_vertices:
            try:
                layer.showLabels = False
            except Exception:
                pass

            for label_class in layer.listLabelClasses():
                try:
                    label_class.visible = False
                except Exception:
                    pass
        arcpy.AddMessage('Rotulos automaticos de vertices removidos da planta principal.')
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel ajustar rotulos de vertices: {str(e)}')

def __limpar_rotulos_mapa_principal(aprx_map: _mp.MapFrame) -> None:
    try:
        for layer in aprx_map.listLayers():
            nome = layer.name.lower()
            if (
                nome.startswith('confrontantes')
                or nome.startswith('logradouro')
                or 'eixo' in nome
            ):
                try:
                    layer.showLabels = False
                    for label_class in layer.listLabelClasses():
                        label_class.visible = False
                except Exception:
                    pass
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel limpar rotulos do mapa principal: {str(e)}')

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

    map_scale_rounded_up = map_scale*1.35
    map_scale_rounded_up = ((((map_scale_rounded_up) // 50) + 1 ) * 50)
    arcpy.AddMessage(f'A escala de visualização do mapa ajustada para {map_scale_rounded_up}')
    map_frame_planta.camera.scale = map_scale_rounded_up
    extent_map_frame = map_frame_planta.camera.getExtent()
    map_frame_planta.camera.setExtent(extent_map_frame)
    arcpy.AddMessage(f'A escala de visualização do mapa ajustada')

def __ajustar_textos_layout(
    layout_planta: _mp.Layout,
    bairro: str,
    municipio: str,
    area: str,
    matricula: str,
    folha: str,
    perimetro: str,
    data: str,
    fusoutm: str,
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
        bairro: str
            Bairro do núcleo.
        municipio: str
            Município do bairro.
        area: str
            Área do bairro.
        matricula: str
            Matrícula do bairro.
        folha: str
            Folha da planta.
        perimetro: str
            Perímetro do bairro.
        data: str
            Data da geração da planta.
        fusoutm: str
            Fuso UTM do bairro.
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
        '{bairro}': bairro,
        '{municipio}': municipio,
        '{area}': area,
        '{matricula}': matricula,
        '{folha}': folha,
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
    layout_planta: _mp.Layout,
    tabela_confrontantes: os.PathLike = None,
    tipo_planta: str = 'simplificada'
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
    tabelas = layout_planta.listElements(
        element_type='TABLEFRAME_ELEMENT',
        wildcard='tabela_dados'
    )
    if tabelas:
        try:
            tabelas[0].visible = False
            arcpy.AddMessage('Quadro de coordenadas ocultado na prancha principal.')
        except Exception as e:
            arcpy.AddWarning(f'Nao foi possivel ocultar quadro de coordenadas: {str(e)}')

    __forcar_aviso_apendice(layout_planta, tipo_planta=tipo_planta)
    return layout_planta

    dict_fields = {
        'de': 'De',
        'para': 'Para',
        'azimute': 'Azim.',
        'dist_txt': 'Dist.',
        'E_txt': 'E',
        'N_txt': 'N'
    }
    larguras = {
        'de': 30,
        'para': 30,
        'azimute': 56,
        'dist_txt': 36,
        'E_txt': 48,
        'N_txt': 52
    }
    map_frame = layout_planta.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard='MAP_FRAME'
    )[0]

    if tabela_confrontantes and arcpy.Exists(tabela_confrontantes):
        lyr = map_frame.map.addDataFromPath(tabela_confrontantes)
        lyr.name = 'quadro_resumido_planta'
        try:
            lyr.visible = False
        except Exception:
            pass
    else:
        lyrs = map_frame.map.listLayers('confrontantes_bairro_final*')
        if not lyrs:
            lyrs = [
                layer for layer in map_frame.map.listLayers()
                if layer.name.startswith('confrontantes_bairro_final')
            ]
        lyr = lyrs[0]
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

    tabela.setAnchor('CENTER_POINT')

    cim_tabela = tabela.getDefinition('V3')

    for prop in ['rowHeight', 'bodyRowHeight', 'dataRowHeight', 'minimumRowHeight']:
        try:
            if hasattr(cim_tabela, prop):
                setattr(cim_tabela, prop, ALTURA_LINHA_QUADRO)
        except Exception:
            pass

    # Configurar nomes de exibição e centralizar valores
    for field in cim_tabela.fields:
        nome = getattr(field, 'name', None) or getattr(field, 'fieldName', None)

        if nome in dict_fields:
            for prop in ['heading', 'headingText', 'alias', 'displayName', 'fieldAlias']:
                try:
                    if hasattr(field, prop):
                        setattr(field, prop, dict_fields[nome])
                except Exception:
                    pass

        if nome in larguras:
            for prop in ['width', 'columnWidth', 'fieldWidth']:
                try:
                    if hasattr(field, prop):
                        setattr(field, prop, larguras[nome])
                except Exception:
                    pass

        if hasattr(field, 'textSymbol') and field.textSymbol is not None:
            __ajustar_tamanho_texto(field.textSymbol, FONTE_QUADRO_CORPO)

        if hasattr(field, 'headingTextSymbol') and field.headingTextSymbol is not None:
            __ajustar_tamanho_texto(field.headingTextSymbol, FONTE_QUADRO_CABECALHO)

        if getattr(field, 'name', None) in ['distancia', 'E', 'N', 'dist_txt', 'E_txt', 'N_txt']:
            try:
                numeric_format = CIMNumericFormat()
                numeric_format.roundingOption = 'esriRoundNumberOfDecimals'
                numeric_format.roundingValue = 4
                numeric_format.showThousandsSeparator = False
                field.numberFormat = numeric_format
            except Exception:
                pass

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
    __forcar_aviso_apendice(layout_planta, tipo_planta=tipo_planta)

    return layout_planta

def exportar_planta_para_pdf(
    layout_planta: _mp.Layout,
    numero_reurb_coletivo: str,
    sufixo: str = ''
) -> os.PathLike:
    """
    Exporta a planta para PDF
    
    -------
    Args:
        layout_planta: _mp.Layout
            Layout da planta.
        numero_reurb_coletivo: str
            Número do REURB coletivo.

    -------
    Returns:
        os.PathLike:
            Caminho para o PDF da planta.
    """
    arcpy.AddMessage(f'Exportando a planta para PDF')
    nome_base = f'planta_{numero_reurb_coletivo.replace("/", "_")}'
    if sufixo:
        nome_base = f'{nome_base}_{sufixo}'
    pdf_path = os.path.join(
        arcpy.env.scratchFolder,
        f'{nome_base}.pdf'
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
    bairro_selecionado: os.PathLike,
    confrontantes_bairro: os.PathLike,
    vertices_bairro: os.PathLike,
    eixo_viario: os.PathLike,
    tabela_confrontantes: os.PathLike,
    bairro_layout: os.PathLike,
    bairro: str,
    municipio: str,
    area: str,
    matricula: str,
    folha: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    tipo_planta: str = 'simplificada'
) -> _mp.Layout:
    """
    Gera a planta
    
    -------
    Args:
        bairro_selecionado: os.PathLike
            Caminho para a camada do bairro selecionado.
        confrontantes_bairro: os.PathLike
            Caminho para a camada dos confrontantes do bairro.
        vertices_bairro: os.PathLike
            Caminho para a camada dos vértices do bairro.
        lotes_layout: os.PathLike
            Caminho para a camada do bairro layout.
        bairro: str
            Nome do bairro.
        municipio: str
            Município do bairro.
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
        bairro_selecionado: simbologia_perimetro,
        confrontantes_bairro: simbologia_confrontantes,
        vertices_bairro: simbologia_vertices
    }

    for camada, simbologia in camadas_map_frame.items():
        __adicionar_camada(
            aprx_map=map_frame_planta,
            feature=camada,
            simbologia=simbologia
        )

    __limpar_rotulos_mapa_principal(map_frame_planta)
    __reduzir_rotulos_vertices(map_frame_planta)

    __adicionar_eixo_viario_rotulos(
        aprx_map=map_frame_planta,
        eixo_viario=eixo_viario
    )

    #Adicionar camadas ao overview
    camadas_overview = {
        bairro_selecionado: simbologia_perimetro_overview
    }

    for camada, simbologia in camadas_overview.items():
        __adicionar_camada(
            aprx_map=map_overview_planta,
            feature=camada,
            simbologia=simbologia
        )

    map_overview_planta.addDataFromPath(r'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer')

    #Ajustar escala de visualização do map frame e overview
    #map_frame
    __ajustar_escala_visualizacao(
        aprx_map=map_frame_planta,
        layout_planta=layout_planta,
        feature_extend=bairro_selecionado,
        element_wildcard='MAP_FRAME'
    )

    #overview
    __ajustar_escala_visualizacao(
        aprx_map=map_overview_planta,
        layout_planta=layout_planta,
        feature_extend=bairro_layout,
        element_wildcard='OVERVIEW_MAP_FRAME'
    )

    #Ajustar textos do layout
    layout_planta = __ajustar_textos_layout(
        layout_planta=layout_planta,
        bairro=bairro,
        municipio=municipio,
        area=area,
        matricula=matricula,
        folha=folha,
        perimetro=perimetro,
        data=data,
        fusoutm=fusoutm,
        responsavel_tecnico=responsavel_tecnico,
        funcao=funcao,
        n_crea_cau=n_crea_cau
    )

    #ajustar tabela com dados limitrofes
    layout_planta = __ajustar_tabela_dados(
        layout_planta=layout_planta,
        tabela_confrontantes=tabela_confrontantes,
        tipo_planta=tipo_planta
    )

    return layout_planta
