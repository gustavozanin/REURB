# -*- coding: utf-8 -*-

import math
import os
import base64
import arcpy
from arcpy import _mp
from arcpy.cim import CIMNumericFormat
from typing import Literal, NamedTuple

from caminhos_gerais import projeto_arcgis
from caminho_simbologias import (
    simbologia_bairro_overview,
    simbologia_quadra,
    simbologia_lote,
    simbologia_eixo_viario,
)

CAPACIDADE_BASE = 76
FONTE_PADRAO = 6.0
FONTE_ABSOLUTA_MINIMA = 3.0
MAX_COLUNAS = 4
COLUMN_GAP_PADRAO = 25
COLUMN_GAP_REDUCIDO = 10
# Anexo: o frame de 315,7 x 261,0 mm em A3 comporta 64 linhas legíveis por
# seção com fonte de 6 pt. Duas seções lado a lado é o limite: com três, os
# seis campos (incluindo nome e status) não cabem na largura disponível.
CAPACIDADE_ANEXO_POR_SECAO = 64
MAX_SECOES_ANEXO = 2
MAX_LINHAS_ANEXO = CAPACIDADE_ANEXO_POR_SECAO * MAX_SECOES_ANEXO
NOME_LAYOUT_PLANTA = 'Layout_Planta_Loteamento_A3'
NOME_LAYOUT_ANEXO = 'Layout_Anexo_Tabela_A3'
NOME_MAPA_PRINCIPAL = 'MAP_FRAME'
FORMATOS_TABELA = {
    'area_m2': 2,
    'qtd_lotes': 0,
}
CAMPOS_TABELA_LOTES = {
    'quadra': 'Quadra',
    'lote': 'Lote',
    'nome': 'Nome do Interessado',
    'cpf_cnpj': 'CPF/CNPJ',
    'status_txt': 'Status de andamento',
    'situacao_txt': 'Situação',
}


class LayoutTabela(NamedTuple):
    colunas: int
    fonte: float
    column_gap: float
    min_font_size: float
    linhas_por_coluna: int


def formatar_numero_br(valor, casas: int = 2) -> str:
    """
    Formata medidas do carimbo na convenção brasileira (1.234,56).

    Mesmo formato do Núcleo e do memorial, para que o mesmo número apareça
    igual nos documentos do processo.
    """
    if valor is None or valor == '':
        return ''
    return (
        f'{float(valor):,.{casas}f}'
        .replace(',', 'X')
        .replace('.', ',')
        .replace('X', '.')
    )


def __ajustar_numero_folha(layout: _mp.Layout, folha: str) -> None:
    """Atualiza somente o número da folha, preservando os demais textos."""
    elementos = layout.listElements(
        element_type='TEXT_ELEMENT',
        wildcard='{folha}'
    )
    if not elementos:
        arcpy.AddWarning('Elemento {folha} não encontrado no layout.')
        return
    elementos[0].text = folha


def __obter_layout(aprx: arcpy.mp.ArcGISProject, nome: str) -> _mp.Layout:
    for layout in aprx.listLayouts():
        if layout.name == nome:
            return layout
    raise ValueError(f'Layout "{nome}" não encontrado no projeto ArcGIS.')


def __obter_mapa(aprx: arcpy.mp.ArcGISProject, nome: str) -> _mp.Map:
    for mapa in aprx.listMaps():
        if mapa.name == nome:
            return mapa
    raise ValueError(f'Mapa "{nome}" não encontrado no projeto ArcGIS.')


def __obter_dimensoes_frame_mm(cim_tabela) -> tuple[float, float]:
    """Retorna altura e largura do frame da tabela em milímetros."""
    altura_fallback = 143.43
    largura_fallback = 152.46

    frame = getattr(cim_tabela, 'frame', None)
    if frame is None or not getattr(frame, 'rings', None):
        return altura_fallback, largura_fallback

    ring = frame.rings[0]
    xs = [ponto[0] for ponto in ring]
    ys = [ponto[1] for ponto in ring]
    return max(ys) - min(ys), max(xs) - min(xs)


def __calcular_layout_tabela(
    n_linhas: int,
    altura_mm: float,
    largura_mm: float
) -> LayoutTabela:
    del altura_mm, largura_mm

    if n_linhas <= 0:
        n_linhas = 1

    n_colunas = max(1, math.ceil(n_linhas / CAPACIDADE_BASE))
    n_colunas = min(n_colunas, MAX_COLUNAS)
    linhas_por_coluna = math.ceil(n_linhas / n_colunas)

    if linhas_por_coluna <= CAPACIDADE_BASE:
        fonte = FONTE_PADRAO
    else:
        fonte = FONTE_PADRAO * CAPACIDADE_BASE / linhas_por_coluna

    fonte = round(min(FONTE_PADRAO, max(FONTE_ABSOLUTA_MINIMA, fonte)), 2)
    fonte = math.floor(fonte * 10) / 10
    column_gap = COLUMN_GAP_REDUCIDO if n_colunas > 1 else COLUMN_GAP_PADRAO

    return LayoutTabela(
        colunas=n_colunas,
        fonte=fonte,
        column_gap=column_gap,
        min_font_size=FONTE_ABSOLUTA_MINIMA,
        linhas_por_coluna=linhas_por_coluna
    )


def __definir_altura_fonte_simbolo(simbolo_ref, altura: float) -> None:
    if simbolo_ref is None:
        return

    simbolo = getattr(simbolo_ref, 'symbol', None)
    if simbolo is not None and hasattr(simbolo, 'height'):
        simbolo.height = altura


def __aplicar_fonte_tabela_cim(cim_tabela, fonte: float) -> None:
    campo_padrao = getattr(cim_tabela, 'defaultTableFrameField', None)
    if campo_padrao is not None:
        __definir_altura_fonte_simbolo(campo_padrao.textSymbol, fonte)
        __definir_altura_fonte_simbolo(campo_padrao.headingTextSymbol, fonte)

    for field in getattr(cim_tabela, 'fields', []) or []:
        __definir_altura_fonte_simbolo(field.textSymbol, fonte)
        __definir_altura_fonte_simbolo(field.headingTextSymbol, fonte)


def __criar_formato_numerico(casas_decimais: int) -> CIMNumericFormat:
    formato = CIMNumericFormat()
    formato.roundingOption = 'esriRoundNumberOfDecimals'
    formato.roundingValue = casas_decimais
    formato.alignmentOption = 'esriAlignCenter'
    formato.alignmentWidth = casas_decimais
    formato.useSeparator = False
    formato.zeroPad = True
    return formato


def __aplicar_formato_campos_tabela(cim_tabela) -> None:
    for field in getattr(cim_tabela, 'fields', []) or []:
        casas_decimais = FORMATOS_TABELA.get(field.name)
        if casas_decimais is not None:
            field.numberFormat = __criar_formato_numerico(casas_decimais)


def __adicionar_camada(
    aprx_map: _mp.Map,
    feature: os.PathLike,
    simbologia: os.PathLike
) -> None:
    """Adiciona uma camada ao mapa com simbologia opcional."""
    arcpy.AddMessage(f'Adicionando a camada: {feature}')

    if simbologia and not os.path.exists(simbologia):
        arcpy.AddWarning(f'Arquivo de simbologia não encontrado: {simbologia}')

    if int(arcpy.management.GetCount(feature)[0]):
        layer = aprx_map.addDataFromPath(feature)

        if simbologia and os.path.exists(simbologia):
            try:
                arcpy.ApplySymbologyFromLayer_management(
                    in_layer=layer,
                    in_symbology_layer=simbologia,
                    symbology_fields=None,
                    update_symbology='DEFAULT'
                )
            except Exception as e:
                arcpy.AddWarning(f'Erro ao aplicar simbologia: {str(e)}')
        else:
            arcpy.AddMessage('Simbologia não aplicada (arquivo não encontrado)')

        try:
            layer.showLabels = True
        except Exception:
            pass

    arcpy.AddMessage(f'Camada adicionada: {feature}')


def __adicionar_limite_bairro(
    aprx_map: _mp.Map,
    feature: os.PathLike
) -> None:
    """Coloca o perímetro no mapa principal como polígono (igual ao núcleo)."""
    if not int(arcpy.management.GetCount(feature)[0]):
        return

    layer = aprx_map.addDataFromPath(feature)
    layer.name = 'Limite do Bairro'
    layer.showInLegend = True

    try:
        symbology = layer.symbology
        symbology.updateRenderer('SimpleRenderer')
        symbol = symbology.renderer.symbol
        symbol.color = {'RGB': [230, 0, 0, 0]}
        symbol.outlineColor = {'RGB': [230, 0, 0, 100]}
        symbol.outlineWidth = 2
        layer.symbology = symbology
        arcpy.AddMessage('Limite do Bairro desenhado como polígono')
    except Exception as e:
        arcpy.AddWarning(f'Não foi possível desenhar o limite como polígono: {e}')


def __ajustar_escala_visualizacao(
    aprx_map: _mp.Map,
    layout_planta: _mp.Layout,
    feature_extend: os.PathLike,
    element_wildcard: Literal['MAP_FRAME', 'OVERVIEW_MAP_FRAME'] = None
) -> None:
    """Ajusta a escala de visualização do mapa."""
    arcpy.AddMessage('Ajustando a escala de visualização do mapa')
    extent = arcpy.Describe(value=feature_extend).extent
    map_frame_planta = layout_planta.listElements(
        element_type="MAPFRAME_ELEMENT",
        wildcard=element_wildcard
    )[0]
    map_frame_planta.map = aprx_map
    map_frame_planta.camera.setExtent(extent)
    aprx_map.defaultCamera = map_frame_planta.camera
    map_scale = map_frame_planta.camera.scale

    map_scale_rounded_up = ((((map_scale * 1.2) // 50) + 1) * 50)
    arcpy.AddMessage(f'A escala de visualização do mapa ajustada para {map_scale_rounded_up}')
    map_frame_planta.camera.scale = map_scale_rounded_up
    extent_map_frame = map_frame_planta.camera.getExtent()
    map_frame_planta.camera.setExtent(extent_map_frame)
    arcpy.AddMessage('A escala de visualização do mapa ajustada')


def __ajustar_textos_layout(
    layout_planta: _mp.Layout,
    bairro: str,
    municipio: str,
    processo: str,
    area: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    area_total_quadra: float,
    qtd_total_quadra: int,
    escala: str = ''
) -> _mp.Layout:
    """Ajusta os textos do layout."""
    dict_alteracoes_textos = {
        '{bairro}': bairro,
        '{municipio}': municipio,
        '{processo}': processo,
        '{area}': formatar_numero_br(area),
        '{perimetro}': formatar_numero_br(perimetro),
        '{data}': data,
        '{fusoutm}': fusoutm,
        '{responsavel_tecnico}': responsavel_tecnico,
        '{funcao}': funcao,
        '{n_crea_cau}': n_crea_cau,
        '{area_total_quadra}': formatar_numero_br(area_total_quadra),
        '{qtd_total_quadra}': formatar_numero_br(qtd_total_quadra, casas=0),
        # Total de folhas só é conhecido na exportação, que reescreve o campo.
        '{folha}': '01',
        '{escala}': escala,
    }

    for elemento, valor in dict_alteracoes_textos.items():
        textos = layout_planta.listElements(
            element_type="TEXT_ELEMENT",
            wildcard=f'{elemento}'
        )
        if not textos:
            continue
        texto_layout = textos[0]
        arcpy.AddMessage(f'Ajustando o texto {texto_layout.text} do layout')
        texto_layout.text = str(valor)
        arcpy.AddMessage(f'O texto {elemento} ajustado para {valor}')

    if escala:
        for elemento in layout_planta.listElements(element_type='TEXT_ELEMENT'):
            texto = elemento.text or ''
            if '{escala}' in texto:
                elemento.text = texto.replace('{escala}', escala)

    return layout_planta


def __ajustar_legenda(
    layout_planta: _mp.Layout,
    aprx_map: _mp.Map
) -> _mp.Layout:
    """Mostra na legenda lotes, quadras e limite do bairro (polígonos)."""
    nomes_legenda = {
        'lote_layout': 'Lotes',
        'quadra_layout': 'Quadras',
        'limite_bairro_layout': 'Limite do Bairro',
        'Lotes': 'Lotes',
        'Quadras': 'Quadras',
        'Limite do Bairro': 'Limite do Bairro',
    }
    camadas_sem_legenda = ('eixo_viario_layout',)

    for camada in aprx_map.listLayers():
        nome_interno = camada.name
        try:
            nome_fonte = os.path.basename(camada.dataSource)
        except Exception:
            nome_fonte = ''

        if nome_interno in nomes_legenda or nome_fonte in nomes_legenda:
            chave = nome_interno if nome_interno in nomes_legenda else nome_fonte
            camada.showInLegend = True
            camada.name = nomes_legenda[chave]
        elif nome_interno in camadas_sem_legenda or nome_fonte in camadas_sem_legenda:
            camada.showInLegend = False

    camada_quadra = None
    camada_bairro = None
    camada_lote = None
    for camada in aprx_map.listLayers():
        if camada.name == 'Quadras':
            camada_quadra = camada
        elif camada.name == 'Limite do Bairro':
            camada_bairro = camada
        elif camada.name == 'Lotes':
            camada_lote = camada
    if camada_quadra is not None and camada_bairro is not None:
        aprx_map.moveLayer(camada_bairro, camada_quadra, 'BEFORE')
    if camada_quadra is not None and camada_lote is not None:
        aprx_map.moveLayer(camada_lote, camada_quadra, 'BEFORE')

    legendas = layout_planta.listElements(element_type='LEGEND_ELEMENT')
    if not legendas:
        arcpy.AddWarning('Elemento de legenda não encontrado no layout.')
        return layout_planta

    for item in legendas[0].items:
        nome = (item.name or '').lower()
        item.visible = 'eixo' not in nome

    arcpy.AddMessage(
        'Legenda ajustada: Lotes, Quadras e Limite do Bairro'
    )

    return layout_planta


def __ajustar_tabela_quadras(
    layout_planta: _mp.Layout
) -> _mp.Layout:
    """Ajusta a tabela com resumo de quadras ordenadas por quadra."""
    dict_fields = {
        'quadra': 'Quadra',
        'area_m2': 'Área (m²)',
        'qtd_lotes': 'Qtd. de Lotes'
    }
    map_frame = layout_planta.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard='MAP_FRAME'
    )[0]

    lyr = map_frame.map.listLayers('quadra_layout')[0]
    n_linhas = int(arcpy.management.GetCount(lyr)[0])

    tabela = layout_planta.listElements(
        element_type='TABLEFRAME_ELEMENT',
        wildcard='tabela_dados'
    )[0]

    tabela.table = lyr
    tabela.fields = list(dict_fields.keys())
    tabela.setAnchor('CENTER_POINT')

    cim_tabela = tabela.getDefinition('V3')
    for field in cim_tabela.fields:
        field.displayName = dict_fields[field.name]

    altura_mm, largura_mm = __obter_dimensoes_frame_mm(cim_tabela)
    layout_tabela = __calcular_layout_tabela(
        n_linhas=n_linhas,
        altura_mm=altura_mm,
        largura_mm=largura_mm
    )

    cim_tabela.columns = layout_tabela.colunas
    cim_tabela.minFontSize = layout_tabela.min_font_size
    cim_tabela.fillingStrategy = 'ShowAllRows'
    cim_tabela.fittingStrategy = 'AdjustColumnsAndSize'
    cim_tabela.columnGap = layout_tabela.column_gap
    cim_tabela.balanceColumns = True

    __aplicar_fonte_tabela_cim(cim_tabela, layout_tabela.fonte)
    __aplicar_formato_campos_tabela(cim_tabela)

    for field in cim_tabela.fields:
        if hasattr(field, 'textSymbol') and field.textSymbol is not None:
            try:
                if hasattr(field.textSymbol, 'symbol'):
                    if hasattr(field.textSymbol.symbol, 'horizontalAlignment'):
                        field.textSymbol.symbol.horizontalAlignment = 'Center'
            except Exception:
                pass

        if hasattr(field, 'headingTextSymbol') and field.headingTextSymbol is not None:
            try:
                if hasattr(field.headingTextSymbol, 'symbol'):
                    if hasattr(field.headingTextSymbol.symbol, 'horizontalAlignment'):
                        field.headingTextSymbol.symbol.horizontalAlignment = 'Center'
            except Exception:
                pass

    tabela.setDefinition(cim_tabela)

    arcpy.AddMessage(
        'Tabela de quadras ajustada: '
        f'{n_linhas} linhas, '
        f'{layout_tabela.colunas} coluna(s), '
        f'fonte {layout_tabela.fonte} pt, '
        f'~{layout_tabela.linhas_por_coluna} linhas/coluna'
    )

    return layout_planta


def __configurar_table_frame_anexo(
    tabela,
    lyr,
    campos: dict,
    n_linhas: int
) -> int:
    """Configura o TableFrame do anexo, sem redimensionar o frame.

    Distribui as linhas em seções lado a lado e retorna quantas foram usadas.
    """
    tabela.table = lyr
    tabela.fields = list(campos.keys())

    cim_tabela = tabela.getDefinition('V3')
    for field in getattr(cim_tabela, 'fields', []) or []:
        if field.name in campos:
            field.displayName = campos[field.name]

    secoes = max(1, math.ceil(n_linhas / CAPACIDADE_ANEXO_POR_SECAO))
    secoes = min(secoes, MAX_SECOES_ANEXO)

    # 'columns' é o limite de seções que o Pro pode usar para encaixar as
    # linhas: com o valor em 1 ele nunca preenche a largura restante do frame.
    cim_tabela.columns = secoes
    cim_tabela.minFontSize = FONTE_PADRAO
    cim_tabela.fillingStrategy = 'ShowAllRows'
    cim_tabela.fittingStrategy = 'AdjustColumns'
    cim_tabela.columnGap = (
        COLUMN_GAP_REDUCIDO if secoes > 1 else COLUMN_GAP_PADRAO
    )
    cim_tabela.balanceColumns = secoes > 1

    __aplicar_fonte_tabela_cim(cim_tabela, FONTE_PADRAO)

    for field in getattr(cim_tabela, 'fields', []) or []:
        if hasattr(field, 'textSymbol') and field.textSymbol is not None:
            try:
                if hasattr(field.textSymbol, 'symbol'):
                    if hasattr(field.textSymbol.symbol, 'horizontalAlignment'):
                        field.textSymbol.symbol.horizontalAlignment = 'Center'
            except Exception:
                pass

        if hasattr(field, 'headingTextSymbol') and field.headingTextSymbol is not None:
            try:
                if hasattr(field.headingTextSymbol, 'symbol'):
                    if hasattr(field.headingTextSymbol.symbol, 'horizontalAlignment'):
                        field.headingTextSymbol.symbol.horizontalAlignment = 'Center'
            except Exception:
                pass

    tabela.setDefinition(cim_tabela)

    return secoes


def __partir_tabela_lotes(
    feicao: os.PathLike,
    max_linhas: int
) -> list:
    """Divide a feição de lotes em chunks para as folhas de anexo."""
    oid_field = arcpy.Describe(feicao).OIDFieldName
    oids = [row[0] for row in arcpy.da.SearchCursor(feicao, [oid_field])]
    if not oids:
        return []

    scratch_gdb = arcpy.env.scratchGDB
    chunks = []
    layer_tmp = arcpy.MakeFeatureLayer_management(
        in_features=feicao,
        out_layer='lotes_anexo_tmp'
    )

    for indice, inicio in enumerate(range(0, len(oids), max_linhas), start=1):
        lote_oids = oids[inicio:inicio + max_linhas]
        where = f"{oid_field} IN ({','.join(str(oid) for oid in lote_oids)})"
        arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=layer_tmp,
            selection_type='NEW_SELECTION',
            where_clause=where
        )
        saida = os.path.join(scratch_gdb, f'anexo_lotes_{indice}')
        if arcpy.Exists(saida):
            arcpy.Delete_management(saida)
        arcpy.CopyFeatures_management(
            in_features=layer_tmp,
            out_feature_class=saida
        )
        chunks.append(saida)

    return chunks


def __ajustar_textos_anexo(
    layout_anexo: _mp.Layout,
    municipio: str,
    processo: str,
    area: str,
    perimetro: str,
    data: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    folha: str,
    bairro: str
) -> None:
    """Preenche os textos dinâmicos do layout anexo."""
    dict_alteracoes = {
        '{municipio}': municipio,
        '{processo}': processo,
        '{area}': formatar_numero_br(area),
        '{perimetro}': formatar_numero_br(perimetro),
        '{data}': data,
        '{responsavel_tecnico}': responsavel_tecnico,
        '{funcao}': funcao,
        '{n_crea_cau}': n_crea_cau,
        '{folha}': folha,
        '{beneficiários}': (
            f'LISTA DE BENEFICIÁRIOS - {bairro} - {municipio}'
        ).upper(),
    }
    for elemento, valor in dict_alteracoes.items():
        textos = layout_anexo.listElements(
            element_type='TEXT_ELEMENT',
            wildcard=elemento
        )
        if textos:
            textos[0].text = str(valor)


def __gerar_pdfs_anexo_tabela(
    aprx: arcpy.mp.ArcGISProject,
    lote_anexo: os.PathLike,
    municipio: str,
    bairro: str,
    numero_reurb_coletivo: str,
    area: str,
    perimetro: str,
    data: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    total_folhas: int
) -> list:
    """Gera PDFs das folhas de anexo da lista de beneficiários."""
    chunks = __partir_tabela_lotes(
        feicao=lote_anexo,
        max_linhas=MAX_LINHAS_ANEXO
    )
    if not chunks:
        return []

    layout_anexo = __obter_layout(aprx, NOME_LAYOUT_ANEXO)
    mapa_principal = __obter_mapa(aprx, NOME_MAPA_PRINCIPAL)

    map_frames = layout_anexo.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard='MAP_FRAME'
    )
    if map_frames:
        map_frames[0].map = mapa_principal
        map_frames[0].visible = False

    pdfs = []
    for indice, chunk in enumerate(chunks, start=1):
        folha = f'{indice + 1:02d}/{total_folhas:02d}'
        layer_name = f'anexo_lotes_{indice}'

        for lyr in list(mapa_principal.listLayers(layer_name)):
            mapa_principal.removeLayer(lyr)

        layer = mapa_principal.addDataFromPath(chunk)
        layer.name = layer_name
        layer.visible = False

        tabela = layout_anexo.listElements(
            element_type='TABLEFRAME_ELEMENT',
            wildcard='tabela_dados'
        )[0]
        tabela.visible = True
        n_linhas = int(arcpy.management.GetCount(chunk)[0])
        secoes = __configurar_table_frame_anexo(
            tabela=tabela,
            lyr=layer,
            campos=CAMPOS_TABELA_LOTES,
            n_linhas=n_linhas
        )

        __ajustar_textos_anexo(
            layout_anexo=layout_anexo,
            municipio=municipio,
            processo=numero_reurb_coletivo,
            area=area,
            perimetro=perimetro,
            data=data,
            responsavel_tecnico=responsavel_tecnico,
            funcao=funcao,
            n_crea_cau=n_crea_cau,
            folha=folha,
            bairro=bairro
        )

        pdf_path = os.path.join(
            arcpy.env.scratchFolder,
            f'anexo_lotes_{numero_reurb_coletivo.replace("/", "_")}'
            f'_{indice + 1:02d}.pdf'
        )
        layout_anexo.exportToPDF(out_pdf=pdf_path)
        pdfs.append(pdf_path)

        arcpy.AddMessage(
            f'Anexo folha {folha} exportado: {n_linhas} linhas, '
            f'{secoes} seção(ões) lado a lado, fonte {FONTE_PADRAO} pt'
        )

        mapa_principal.removeLayer(layer)

    return pdfs


def __unir_pdfs(pdf_paths: list, pdf_saida: os.PathLike) -> os.PathLike:
    """Une uma lista de PDFs em um único arquivo."""
    if len(pdf_paths) == 1:
        if os.path.abspath(pdf_paths[0]) != os.path.abspath(pdf_saida):
            import shutil
            shutil.copy2(pdf_paths[0], pdf_saida)
        return pdf_saida

    if os.path.exists(pdf_saida):
        arcpy.Delete_management(pdf_saida)

    pdf_doc = arcpy.mp.PDFDocumentCreate(pdf_saida)
    for pdf_path in pdf_paths:
        pdf_doc.appendPages(str(pdf_path))
    pdf_doc.saveAndClose()
    arcpy.AddMessage(f'PDF unificado com {len(pdf_paths)} página(s): {pdf_saida}')
    return pdf_saida


def exportar_planta_para_pdf(
    layout_planta: _mp.Layout,
    aprx: arcpy.mp.ArcGISProject,
    numero_reurb_coletivo: str,
    lote_anexo: os.PathLike,
    municipio: str,
    bairro: str,
    area: str,
    perimetro: str,
    data: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str
) -> os.PathLike:
    """Exporta a planta para PDF e anexa as folhas da lista de beneficiários."""
    arcpy.AddMessage('Exportando a planta para PDF')
    pdf_final = os.path.join(
        arcpy.env.scratchFolder,
        f'planta_loteamento_{numero_reurb_coletivo.replace("/", "_")}.pdf'
    )
    pdf_principal = os.path.join(
        arcpy.env.scratchFolder,
        f'planta_{numero_reurb_coletivo.replace("/", "_")}_folha01.pdf'
    )
    n_linhas = int(arcpy.management.GetCount(lote_anexo)[0])
    total_folhas = 1 + math.ceil(n_linhas / MAX_LINHAS_ANEXO)
    # A folha 01 só sabe o total depois de contar os anexos, por isso a
    # numeração é escrita aqui, e não ao montar o layout.
    __ajustar_numero_folha(layout_planta, f'01/{total_folhas:02d}')
    layout_planta.exportToPDF(out_pdf=pdf_principal)

    pdfs = [pdf_principal]

    arcpy.AddMessage(
        f'Gerando anexos da lista de beneficiários ({n_linhas} linhas, '
        f'máx. {MAX_LINHAS_ANEXO} por folha)'
    )
    pdfs.extend(
        __gerar_pdfs_anexo_tabela(
            aprx=aprx,
            lote_anexo=lote_anexo,
            numero_reurb_coletivo=numero_reurb_coletivo,
            municipio=municipio,
            bairro=bairro,
            area=area,
            perimetro=perimetro,
            data=data,
            responsavel_tecnico=responsavel_tecnico,
            funcao=funcao,
            n_crea_cau=n_crea_cau,
            total_folhas=total_folhas
        )
    )

    __unir_pdfs(pdfs, pdf_final)
    arcpy.AddMessage('Planta exportada para PDF')
    return pdf_final


def converter_base64(
    file: os.PathLike
) -> str:
    """Converte um arquivo para base64."""
    arcpy.AddMessage('Convertendo o arquivo para base64')
    with open(file, "rb") as _file:
        encoded_string = str(base64.b64encode(_file.read()), "UTF8")
    arcpy.AddMessage('Arquivo convertido para base64')

    return encoded_string


def gerar_planta(
    bairro_selecionado: os.PathLike,
    bairro_layout: os.PathLike,
    quadra_layout: os.PathLike,
    lote_layout: os.PathLike,
    eixo_viario_layout: os.PathLike,
    bairro: str,
    municipio: str,
    numero_reurb_coletivo: str,
    area: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    area_total_quadra: float,
    qtd_total_quadra: int
) -> tuple:
    """
    Gera a planta do loteamento com mapa principal, mapa de localização
    e tabela resumo de quadras.
    """
    aprx = arcpy.mp.ArcGISProject(aprx_path=projeto_arcgis)

    map_frame_planta = __obter_mapa(aprx, NOME_MAPA_PRINCIPAL)
    map_overview_planta = __obter_mapa(aprx, 'OVERVIEW_MAP_FRAME')
    layout_planta = __obter_layout(aprx, NOME_LAYOUT_PLANTA)

    # Eixo, lotes e limite embaixo; quadra por cima do bairro.
    camadas_map_frame = [
        (eixo_viario_layout, simbologia_eixo_viario),
        (lote_layout, simbologia_lote),
    ]

    for camada, simbologia in camadas_map_frame:
        __adicionar_camada(
            aprx_map=map_frame_planta,
            feature=camada,
            simbologia=simbologia
        )

    __adicionar_limite_bairro(
        aprx_map=map_frame_planta,
        feature=bairro_layout
    )
    __adicionar_camada(
        aprx_map=map_frame_planta,
        feature=quadra_layout,
        simbologia=simbologia_quadra
    )

    __adicionar_camada(
        aprx_map=map_overview_planta,
        feature=bairro_layout,
        simbologia=simbologia_bairro_overview
    )

    # Basemap local/portal pode não ter "Imagery"; usa serviço público como no Núcleo
    try:
        map_overview_planta.addDataFromPath(
            r'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
        )
    except Exception as e:
        arcpy.AddWarning(
            f'Não foi possível adicionar imagem de satélite no overview ({e}). '
            f'Continuando sem basemap.'
        )

    __ajustar_escala_visualizacao(
        aprx_map=map_frame_planta,
        layout_planta=layout_planta,
        feature_extend=bairro_selecionado,
        element_wildcard='MAP_FRAME'
    )
    mapa_principal = layout_planta.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard='MAP_FRAME',
    )[0]
    escala_txt = '1:' + (
        f'{int(round(mapa_principal.camera.scale)):,}'.replace(',', '.')
    )

    __ajustar_escala_visualizacao(
        aprx_map=map_overview_planta,
        layout_planta=layout_planta,
        feature_extend=bairro_layout,
        element_wildcard='OVERVIEW_MAP_FRAME'
    )

    layout_planta = __ajustar_textos_layout(
        layout_planta=layout_planta,
        bairro=bairro,
        municipio=municipio,
        processo=numero_reurb_coletivo,
        area=area,
        perimetro=perimetro,
        data=data,
        fusoutm=fusoutm,
        responsavel_tecnico=responsavel_tecnico,
        funcao=funcao,
        n_crea_cau=n_crea_cau,
        area_total_quadra=area_total_quadra,
        qtd_total_quadra=qtd_total_quadra,
        escala=escala_txt,
    )

    layout_planta = __ajustar_tabela_quadras(
        layout_planta=layout_planta
    )

    layout_planta = __ajustar_legenda(
        layout_planta=layout_planta,
        aprx_map=map_frame_planta
    )

    return layout_planta, aprx
