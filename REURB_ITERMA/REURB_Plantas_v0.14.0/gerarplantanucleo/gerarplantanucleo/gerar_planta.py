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
    simbologia_vertices,
    simbologia_perimetro_overview,
    simbologia_quadra,
    simbologia_lote,
)

# Calibração para impressão A3 legível: até 38 linhas por coluna com fonte de 8 pt.
# Acima de duas colunas, o conjunto de seis campos fica estreito demais para leitura.
CAPACIDADE_BASE = 38
FONTE_PADRAO = 8.0
FONTE_ABSOLUTA_MINIMA = 7.0
MAX_COLUNAS = 2
COLUMN_GAP_PADRAO = 25
COLUMN_GAP_REDUCIDO = 10
MAX_LINHAS_ANEXO = int(
    MAX_COLUNAS * CAPACIDADE_BASE * (FONTE_PADRAO / FONTE_ABSOLUTA_MINIMA)
)
AVISO_TABELA_ANEXO = (
    'A tabela de vértices encontra-se nas páginas em anexo.'
)
NOME_LAYOUT_PLANTA = 'Layout_Planta_Nucleo_A3'
NOME_LAYOUT_ANEXO = 'Layout_Anexo_Tabela_A3'
NOME_MAPA_PRINCIPAL = 'MAP_FRAME'
NOME_MAPA_OVERVIEW = 'OVERVIEW_MAP_FRAME'
FORMATOS_TABELA_QUADRAS = {
    'area_m2': 2,
    'qtd_lotes': 0,
}
FORMATOS_TABELA_VERTICES = {
    'distancia': 2,
    'E': 4,
    'N': 4,
}
CAMPOS_TABELA_QUADRAS = {
    'quadra': 'Quadra',
    'area_m2': 'Área (m²)',
    'qtd_lotes': 'Qtd. de Lotes'
}
CAMPOS_TABELA_VERTICES = {
    'de': 'De',
    'para': 'Para',
    'azimute': 'Azimute',
    'distancia': 'Distância',
    'E': 'E (x)',
    'N': 'N (y)'
}


class LayoutTabela(NamedTuple):
    colunas: int
    fonte: float
    column_gap: float
    min_font_size: float
    linhas_por_coluna: int


def __obter_layout(aprx: arcpy.mp.ArcGISProject, nome: str) -> _mp.Layout:
    for layout in aprx.listLayouts():
        if layout.name == nome:
            return layout
    raise ValueError(f'Layout "{nome}" não encontrado no projeto ArcGIS.')


def __obter_mapa(aprx: arcpy.mp.ArcGISProject, nome: str) -> arcpy.mp:
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
    """
    Calcula colunas, fonte e espaçamentos para exibir todas as linhas
    no frame disponível da tabela cartográfica.
    """
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
    formato.alignmentWidth = 0
    formato.useSeparator = False
    formato.zeroPad = True
    return formato


def __aplicar_formato_campos_tabela(cim_tabela, formatos: dict) -> None:
    for field in getattr(cim_tabela, 'fields', []) or []:
        casas_decimais = formatos.get(field.name)
        if casas_decimais is not None:
            field.numberFormat = __criar_formato_numerico(casas_decimais)


def __centralizar_textos_campos_tabela(cim_tabela) -> None:
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


def __configurar_table_frame(
    tabela,
    lyr,
    n_linhas: int,
    campos: dict,
    formatos: dict
) -> LayoutTabela:
    """Aplica source, campos, colunas e fonte ao Table Frame."""
    tabela.table = lyr
    tabela.fields = list(campos.keys())
    tabela.setAnchor('CENTER_POINT')

    cim_tabela = tabela.getDefinition('V3')
    for field in getattr(cim_tabela, 'fields', []) or []:
        if field.name in campos:
            field.displayName = campos[field.name]

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
    __aplicar_formato_campos_tabela(cim_tabela, formatos)
    __centralizar_textos_campos_tabela(cim_tabela)
    tabela.setDefinition(cim_tabela)

    return layout_tabela


def __adicionar_camada(
    aprx_map: _mp.MapFrame,
    feature: os.PathLike,
    simbologia: os.PathLike
) -> None:
    """
    Adiciona uma camada ao map frame ou overview
    """
    arcpy.AddMessage(f'Adicionando a camada: {feature}')

    if simbologia and not os.path.exists(simbologia):
        arcpy.AddWarning(f'⚠ Arquivo de simbologia não encontrado: {simbologia}')

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
                arcpy.AddWarning(f'⚠ Erro ao aplicar simbologia: {str(e)}')
        else:
            arcpy.AddMessage('⚠ Simbologia não aplicada (arquivo não encontrado)')

        try:
            layer.showLabels = True
        except Exception:
            pass

    arcpy.AddMessage(f'Camada adicionada: {feature}')


def __adicionar_limite_bairro(aprx_map, feature):
    """Coloca o perímetro no mapa principal como polígono (não como linha)."""
    if not int(arcpy.management.GetCount(feature)[0]):
        return
    layer = aprx_map.addDataFromPath(feature)
    layer.name = 'Limite do Bairro'
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
        if simbologia_perimetro_overview and os.path.exists(
            simbologia_perimetro_overview
        ):
            arcpy.ApplySymbologyFromLayer_management(
                in_layer=layer,
                in_symbology_layer=simbologia_perimetro_overview,
            )


def __ajustar_escala_visualizacao(
    aprx_map: _mp.MapFrame,
    layout_planta: _mp.Layout,
    feature_extend: os.PathLike,
    element_wildcard: Literal['MAP_FRAME', 'OVERVIEW_MAP_FRAME'] = None
) -> None:
    """
    Ajusta a escala de visualização do mapa
    """
    arcpy.AddMessage('Ajustando a escala de visualização do mapa')
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

    map_scale_rounded_up = map_scale * 1.2
    map_scale_rounded_up = ((((map_scale_rounded_up) // 50) + 1) * 50)
    arcpy.AddMessage(f'A escala de visualização do mapa ajustada para {map_scale_rounded_up}')
    map_frame_planta.camera.scale = map_scale_rounded_up
    extent_map_frame = map_frame_planta.camera.getExtent()
    map_frame_planta.camera.setExtent(extent_map_frame)
    arcpy.AddMessage('A escala de visualização do mapa ajustada')


def formatar_numero_br(valor, casas: int = 2) -> str:
    """
    Formata medidas do carimbo na convenção brasileira (1.234,56).

    Mesmo formato do memorial e do quadro, para que o mesmo número apareça
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


def montar_titulo_nucleo(bairro: str) -> str:
    """Título da folha 01 em duas linhas, sem sobreposição no carimbo."""
    nome = '' if bairro is None else str(bairro)
    return f'Planta do Perímetro\nNúcleo Urbano: {nome}'


def montar_textos_anexo(
    municipio: str,
    bairro: str,
    processo: str,
    area,
    perimetro,
    data: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    folha: str,
) -> dict:
    """Valores do carimbo do anexo (inclui Bairro após Município)."""
    return {
        '{municipio}': municipio,
        '{bairro}': bairro,
        '{processo}': processo,
        '{area}': formatar_numero_br(area),
        '{perimetro}': formatar_numero_br(perimetro),
        '{data}': data,
        '{responsavel_tecnico}': responsavel_tecnico,
        '{funcao}': funcao,
        '{n_crea_cau}': n_crea_cau,
        '{folha}': folha,
    }


def __ajustar_textos_layout(
    layout_planta: _mp.Layout,
    area_total_quadra: float,
    qtd_total_quadra: int,
    bairro: str,
    municipio: str,
    area: str,
    processo: str,
    folha: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    escala: str = '',
) -> None:
    """
    Ajusta os textos do layout
    """
    dict_alteracoes_textos = {
        '{area_total_quadra}': formatar_numero_br(area_total_quadra),
        '{qtd_total_quadra}': formatar_numero_br(qtd_total_quadra, casas=0),
        '{titulo_nucleo}': montar_titulo_nucleo(bairro),
        '{bairro}': bairro,
        '{municipio}': municipio,
        '{area}': formatar_numero_br(area),
        '{processo}': processo,
        '{folha}': folha,
        '{perimetro}': formatar_numero_br(perimetro),
        '{data}': data,
        '{fusoutm}': fusoutm,
        '{responsavel_tecnico}': responsavel_tecnico,
        '{funcao}': funcao,
        '{n_crea_cau}': n_crea_cau,
        '{quadra}': '—',
        '{lote}': '—',
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
        texto_layout.text = valor
        arcpy.AddMessage(f'O texto {elemento} ajustado para {valor}')

    for elemento in layout_planta.listElements(element_type='TEXT_ELEMENT'):
        texto = elemento.text or ''
        if '{quadra}' in texto or '{lote}' in texto or '{escala}' in texto:
            novo = (
                texto.replace('{quadra}', '—')
                .replace('{lote}', '—')
            )
            if escala:
                novo = novo.replace('{escala}', escala)
            elemento.text = novo

    return layout_planta


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


def __ajustar_aviso_tabela(layout_planta: _mp.Layout) -> None:
    """Exibe o aviso de que a tabela de vértices está em anexo."""
    elementos = layout_planta.listElements(
        element_type='TEXT_ELEMENT',
        wildcard='{aviso_tabela}'
    )
    if not elementos:
        arcpy.AddWarning('Elemento {aviso_tabela} não encontrado no layout.')
        return

    aviso = elementos[0]
    aviso.text = AVISO_TABELA_ANEXO
    aviso.visible = True
    arcpy.AddMessage('Aviso de tabela em anexo exibido no layout.')


def __ajustar_tabela_quadras(
    layout_planta: _mp.Layout
) -> _mp.Layout:
    """Ajusta a tabela resumo de quadras na folha 1."""
    tabela = layout_planta.listElements(
        element_type='TABLEFRAME_ELEMENT',
        wildcard='tabela_dados'
    )[0]
    tabela.visible = True

    map_frame = layout_planta.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard='MAP_FRAME'
    )[0]
    layers = map_frame.map.listLayers('quadra_layout')
    if not layers:
        arcpy.AddWarning(
            'Camada quadra_layout não encontrada no mapa; '
            'tabela de quadras não foi preenchida.'
        )
        __ajustar_aviso_tabela(layout_planta)
        return layout_planta

    lyr = layers[0]
    n_linhas = int(arcpy.management.GetCount(lyr)[0])
    layout_tabela = __configurar_table_frame(
        tabela=tabela,
        lyr=lyr,
        n_linhas=n_linhas,
        campos=CAMPOS_TABELA_QUADRAS,
        formatos=FORMATOS_TABELA_QUADRAS
    )

    __ajustar_aviso_tabela(layout_planta)

    arcpy.AddMessage(
        'Tabela de quadras ajustada: '
        f'{n_linhas} linhas, '
        f'{layout_tabela.colunas} coluna(s), '
        f'fonte {layout_tabela.fonte} pt, '
        f'~{layout_tabela.linhas_por_coluna} linhas/coluna'
    )

    return layout_planta

def __ajustar_legenda(
    map_frame_planta: _mp.MapFrame,
    layout_planta: _mp.Layout,
    bairro_selecionado: os.PathLike,
    lote_layout: os.PathLike,
    quadra_layout: os.PathLike,
    vertices_bairro: os.PathLike
) -> None:
    """Ajusta a legenda do mapa."""

    def _basename(caminho) -> str:
        if isinstance(caminho, (str, os.PathLike)):
            valor = caminho
        elif hasattr(caminho, 'getOutput'):
            valor = caminho.getOutput(0)
        else:
            try:
                valor = caminho[0]
            except (IndexError, KeyError, TypeError):
                valor = caminho
        return str(os.path.basename(str(valor)))

    def _achar_camada(*trechos: str):
        trechos_l = [t.lower() for t in trechos]
        for lyr in map_frame_planta.listLayers():
            nome = (lyr.name or '').lower()
            if any(t in nome for t in trechos_l):
                return lyr
            try:
                ds = (getattr(lyr, 'dataSource', '') or '').lower().replace('\\', '/')
                if any(t in ds for t in trechos_l):
                    return lyr
            except Exception:
                pass
        return None

    camada_mover = _achar_camada('limite do bairro', 'limite_bairro')
    camada_referencia = _achar_camada('lote')

    dict_nomes_camadas = {
        _basename(lote_layout): 'Lotes',
        _basename(quadra_layout): 'Quadras',
        _basename(vertices_bairro): 'Vértices do limite',
        _basename(bairro_selecionado): 'Limite do Bairro',
    }

    for camada in map_frame_planta.listLayers():
        if camada.name in dict_nomes_camadas:
            camada.name = dict_nomes_camadas[camada.name]
            continue
        try:
            base = os.path.basename(camada.dataSource)
            if base in dict_nomes_camadas:
                camada.name = dict_nomes_camadas[base]
        except Exception:
            pass

    legendas = layout_planta.listElements(
        element_type='LEGEND_ELEMENT',
        wildcard='LEGEND'
    )
    if not legendas:
        arcpy.AddWarning('Elemento LEGEND não encontrado no layout; pulando ajuste.')
        return

    legendas[0].columnCount = 4

    if camada_mover is not None and camada_referencia is not None:
        map_frame_planta.moveLayer(camada_referencia, camada_mover, 'AFTER')
    else:
        nomes = [lyr.name for lyr in map_frame_planta.listLayers()]
        arcpy.AddWarning(
            'Não foi possível reordenar camadas na legenda. '
            f'Camadas no mapa: {nomes}'
        )


def __partir_tabela_vertices(
    feicao: os.PathLike,
    max_linhas: int
) -> list[os.PathLike]:
    """Divide a feição de confrontantes em chunks para as folhas de anexo."""
    oid_field = arcpy.Describe(feicao).OIDFieldName
    oids = [row[0] for row in arcpy.da.SearchCursor(feicao, [oid_field])]
    if not oids:
        return []

    scratch_gdb = arcpy.env.scratchGDB
    chunks = []
    layer_tmp = arcpy.MakeFeatureLayer_management(
        in_features=feicao,
        out_layer='confrontantes_anexo_tmp'
    )

    for indice, inicio in enumerate(range(0, len(oids), max_linhas), start=1):
        lote_oids = oids[inicio:inicio + max_linhas]
        where = f"{oid_field} IN ({','.join(str(oid) for oid in lote_oids)})"
        arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=layer_tmp,
            selection_type='NEW_SELECTION',
            where_clause=where
        )
        saida = os.path.join(scratch_gdb, f'anexo_vertices_{indice}')
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
    bairro: str,
    processo: str,
    area: str,
    perimetro: str,
    data: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str,
    folha: str
) -> None:
    dict_alteracoes = montar_textos_anexo(
        municipio=municipio,
        bairro=bairro,
        processo=processo,
        area=area,
        perimetro=perimetro,
        data=data,
        responsavel_tecnico=responsavel_tecnico,
        funcao=funcao,
        n_crea_cau=n_crea_cau,
        folha=folha,
    )
    for elemento, valor in dict_alteracoes.items():
        textos = layout_anexo.listElements(
            element_type='TEXT_ELEMENT',
            wildcard=elemento
        )
        if textos:
            textos[0].text = valor


def __gerar_pdfs_anexo_tabela(
    aprx: arcpy.mp.ArcGISProject,
    confrontantes_bairro: os.PathLike,
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
) -> list[os.PathLike]:
    """Gera PDFs das folhas de apêndice da tabela de vértices."""
    chunks = __partir_tabela_vertices(
        feicao=confrontantes_bairro,
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
        numero_folha = indice + 1
        folha = f'{numero_folha:02d}/{total_folhas:02d}'
        layer_name = f'anexo_vertices_{indice}'

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
        layout_tabela = __configurar_table_frame(
            tabela=tabela,
            lyr=layer,
            n_linhas=n_linhas,
            campos=CAMPOS_TABELA_VERTICES,
            formatos=FORMATOS_TABELA_VERTICES
        )

        __ajustar_textos_anexo(
            layout_anexo=layout_anexo,
            municipio=municipio,
            bairro=bairro,
            processo=numero_reurb_coletivo,
            area=area,
            perimetro=perimetro,
            data=data,
            responsavel_tecnico=responsavel_tecnico,
            funcao=funcao,
            n_crea_cau=n_crea_cau,
            folha=folha
        )

        pdf_path = os.path.join(
            arcpy.env.scratchFolder,
            f'anexo_vertices_'
            f'{numero_reurb_coletivo.replace("/", "_")}_'
            f'{numero_folha:02d}.pdf'
        )
        layout_anexo.exportToPDF(out_pdf=pdf_path)
        pdfs.append(pdf_path)

        arcpy.AddMessage(
            f'Anexo folha {folha} exportado: {n_linhas} linhas, '
            f'{layout_tabela.colunas} coluna(s), fonte {layout_tabela.fonte} pt'
        )

        mapa_principal.removeLayer(layer)

    return pdfs


def __unir_pdfs(pdf_paths: list[os.PathLike], pdf_saida: os.PathLike) -> os.PathLike:
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
    confrontantes_bairro: os.PathLike,
    municipio: str,
    bairro: str,
    area: str,
    perimetro: str,
    data: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str
) -> os.PathLike:
    """
    Exporta a planta para PDF e anexa as folhas da tabela de vértices.
    """
    arcpy.AddMessage('Exportando a planta para PDF')
    pdf_final = os.path.join(
        arcpy.env.scratchFolder,
        f'planta_geral_{numero_reurb_coletivo.replace("/", "_")}.pdf'
    )
    pdf_principal = os.path.join(
        arcpy.env.scratchFolder,
        f'planta_{numero_reurb_coletivo.replace("/", "_")}_folha01.pdf'
    )
    n_linhas = int(arcpy.management.GetCount(confrontantes_bairro)[0])
    total_anexos = math.ceil(n_linhas / MAX_LINHAS_ANEXO)
    total_folhas = 1 + total_anexos
    __ajustar_numero_folha(layout_planta, f'01/{total_folhas:02d}')
    layout_planta.exportToPDF(out_pdf=pdf_principal)

    pdfs = [pdf_principal]

    arcpy.AddMessage(
        f'Gerando anexos da tabela de vértices ({n_linhas} linhas, '
        f'máx. {MAX_LINHAS_ANEXO} por folha)'
    )
    pdfs.extend(
        __gerar_pdfs_anexo_tabela(
            aprx=aprx,
            confrontantes_bairro=confrontantes_bairro,
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
    """
    Converte um arquivo para base64
    """
    encoded_string = ""
    arcpy.AddMessage('Convertendo o arquivo para base64')
    with open(file, "rb") as _file:
        encoded_string = str(base64.b64encode(_file.read()), "UTF8")
    arcpy.AddMessage('Arquivo convertido para base64')

    return encoded_string


def gerar_planta(
    bairro_selecionado: os.PathLike,
    confrontantes_bairro: os.PathLike,
    vertices_bairro: os.PathLike,
    quadra_layout: os.PathLike,
    lote_layout: os.PathLike,
    area_total_quadra: float,
    qtd_total_quadra: int,
    bairro: str,
    municipio: str,
    area: str,
    processo: str,
    folha: str,
    perimetro: str,
    data: str,
    fusoutm: str,
    responsavel_tecnico: str,
    funcao: str,
    n_crea_cau: str
) -> tuple[_mp.Layout, arcpy.mp.ArcGISProject]:
    """
    Gera a planta do núcleo com perímetro, quadras, lotes e tabela de quadras.
    A tabela de vértices fica sempre nas páginas de anexo.
    """
    aprx = arcpy.mp.ArcGISProject(
        aprx_path=projeto_arcgis
    )

    map_frame_planta = __obter_mapa(aprx, NOME_MAPA_PRINCIPAL)
    map_overview_planta = __obter_mapa(aprx, NOME_MAPA_OVERVIEW)
    layout_planta = __obter_layout(aprx, NOME_LAYOUT_PLANTA)

    __adicionar_limite_bairro(
        aprx_map=map_frame_planta,
        feature=bairro_selecionado,
    )

    camadas_map_frame = [
        (lote_layout, simbologia_lote),
        (quadra_layout, simbologia_quadra),
        (vertices_bairro, simbologia_vertices),
    ]

    for camada, simbologia in camadas_map_frame:
        __adicionar_camada(
            aprx_map=map_frame_planta,
            feature=camada,
            simbologia=simbologia
        )

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
        feature_extend=bairro_selecionado,
        element_wildcard='OVERVIEW_MAP_FRAME'
    )

    layout_planta = __ajustar_textos_layout(
        layout_planta=layout_planta,
        area_total_quadra=area_total_quadra,
        qtd_total_quadra=qtd_total_quadra,
        bairro=bairro,
        municipio=municipio,
        area=area,
        processo=processo,
        folha=folha,
        perimetro=perimetro,
        data=data,
        fusoutm=fusoutm,
        responsavel_tecnico=responsavel_tecnico,
        funcao=funcao,
        n_crea_cau=n_crea_cau,
        escala=escala_txt,
    )

    layout_planta = __ajustar_tabela_quadras(
        layout_planta=layout_planta
    )

    __ajustar_legenda(
        map_frame_planta=map_frame_planta,
        layout_planta=layout_planta,
        bairro_selecionado=bairro_selecionado,
        lote_layout=lote_layout,
        quadra_layout=quadra_layout,
        vertices_bairro=vertices_bairro
    )

    return layout_planta, aprx
