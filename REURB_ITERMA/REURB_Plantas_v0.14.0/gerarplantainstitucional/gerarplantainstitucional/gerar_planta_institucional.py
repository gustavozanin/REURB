# -*- coding: utf-8 -*-
"""Planta A3 de lote institucional — layout igual ao gerarplantareurb.

Usa ``Layout_Planta_Memorial_A`` (planta individual): mapa do lote,
overview da quadra, tabela de confrontantes e carimbo com
interessado/quadra/lote. Rótulos de confrontação reutilizam o pipeline
avançado do memorial (agrupar frente + lado externo).
"""

from __future__ import annotations

import os

import arcpy

from caminhos_gerais import projeto_arcgis, nome_layout_planta
from caminho_simbologias import (
    simbologia_lote,
    simbologia_confrontantes,
    simbologia_vertices,
    simbologia_lote_overview,
    simbologia_quadra_overview,
)
from constantes import (
    COMPRIMENTO_MAX_ROTULO_PONTO_LOTE_M,
    COMPRIMENTO_MINIMO_ROTULO_LINHA_LOTE_M,
    DISTANCIA_MINIMA_ROTULOS_LOTE_M,
)
from gerar_planta_perimetro import (
    AFASTAMENTO_ROTULO_LINHA_PT,
    ALTURA_TEXTO_ROTULO_PT,
    _criar_camadas_rotulos_confrontantes,
    _configurar_rotulos_vertices,
    _definir,
    _ocultar_simbolo_da_camada,
    _classes_por_direcao,
    _classes_por_lado,
)

# Afastamento constante no papel; convertido para metros conforme a escala.
DISTANCIA_ROTULO_EXTERNO_MM = 3.0


def afastamento_mapa_m(escala, distancia_mm=DISTANCIA_ROTULO_EXTERNO_MM):
    """Converte afastamento no papel (mm) para distância no mapa (m)."""
    return float(distancia_mm) * float(escala) / 1000.0

TEXTO_CPF_VAZIO = '—'
TITULO_ESTATICO = 'Planta Institucional para fins de REURB'


def _formatar_numero_br(valor, casas=2) -> str:
    if valor is None or valor == '':
        return ''
    return (
        f'{float(valor):,.{casas}f}'
        .replace(',', 'X')
        .replace('.', ',')
        .replace('X', '.')
    )


def _adicionar_camada(aprx_map, feature, simbologia):
    arcpy.AddMessage(f'Adicionando a camada: {feature}')
    if simbologia and not os.path.exists(simbologia):
        arcpy.AddWarning(f'Arquivo de simbologia não encontrado: {simbologia}')
    if int(arcpy.management.GetCount(feature)[0]) == 0:
        arcpy.AddWarning(f'Camada sem feições, não adicionada: {feature}')
        return None
    layer = aprx_map.addDataFromPath(feature)
    if simbologia and os.path.exists(simbologia):
        try:
            arcpy.ApplySymbologyFromLayer_management(
                in_layer=layer,
                in_symbology_layer=simbologia,
                symbology_fields=None,
                update_symbology='DEFAULT',
            )
        except Exception as e:
            arcpy.AddWarning(f'Erro ao aplicar simbologia: {e}')
    return layer


def _ajustar_escala(aprx_map, layout_planta, feature_extend, element_wildcard) -> None:
    extent = arcpy.Describe(feature_extend).extent
    map_frame = layout_planta.listElements(
        element_type='MAPFRAME_ELEMENT',
        wildcard=element_wildcard,
    )[0]
    map_frame.map = aprx_map
    map_frame.camera.setExtent(extent)
    aprx_map.defaultCamera = map_frame.camera
    escala = ((((map_frame.camera.scale * 1.2) // 50) + 1) * 50)
    map_frame.camera.scale = escala
    map_frame.camera.setExtent(map_frame.camera.getExtent())
    return escala


def _ajustar_textos(
    layout_planta,
    interessado,
    interessado_cpf,
    bairro,
    municipio,
    denominacao,
    quadra,
    lote,
    area,
    perimetro,
    data,
    fusoutm,
    responsavel_tecnico,
    funcao,
    n_crea_cau,
) -> None:
    textos = {
        '{interessado}': interessado or '',
        '{interessado_cpf}': (
            interessado_cpf if interessado_cpf not in (None, '') else TEXTO_CPF_VAZIO
        ),
        '{bairro}': bairro or '',
        '{municipio}': municipio or '',
        '{denominacao}': denominacao or '',
        '{quadra}': str(quadra) if quadra is not None else '',
        '{lote}': str(lote) if lote is not None else '',
        '{area}': area if isinstance(area, str) else _formatar_numero_br(area),
        '{perimetro}': (
            perimetro if isinstance(perimetro, str) else _formatar_numero_br(perimetro)
        ),
        '{data}': data or '',
        '{fusoutm}': fusoutm or '',
        '{responsavel_tecnico}': responsavel_tecnico or '',
        '{funcao}': funcao or '',
        '{n_crea_cau}': n_crea_cau or '',
    }
    for chave, valor in textos.items():
        elementos = layout_planta.listElements(
            element_type='TEXT_ELEMENT',
            wildcard=chave,
        )
        if not elementos:
            arcpy.AddWarning(f'Elemento {chave} não encontrado no layout.')
            continue
        elementos[0].text = '' if valor is None else str(valor)

    for candidato in ('Text 5', TITULO_ESTATICO):
        elementos = layout_planta.listElements(
            element_type='TEXT_ELEMENT',
            wildcard=candidato,
        )
        if elementos:
            elementos[0].text = TITULO_ESTATICO
            break


def _ajustar_tabela(layout_planta) -> None:
    dict_fields = {
        'de': 'De',
        'para': 'Para',
        'azimute': 'Azimute',
        'distancia': 'Distância (m)',
        'e': 'Coord. E (x)',
        'n': 'Coord. N (y)',
        'confrontantes': 'Confrontantes',
    }
    tabelas = layout_planta.listElements(
        element_type='TABLEFRAME_ELEMENT',
        wildcard='tabela_dados',
    )
    if not tabelas:
        arcpy.AddWarning('TableFrame tabela_dados não encontrado no layout.')
        return
    tabela = tabelas[0]
    try:
        for field in tabela.fields:
            nome = field.fieldName.lower() if hasattr(field, 'fieldName') else ''
            if nome in dict_fields:
                field.visible = True
                if hasattr(field, 'heading'):
                    field.heading = dict_fields[nome]
            elif nome in ('objectid', 'shape_length', 'shape'):
                field.visible = False
    except Exception as e:
        arcpy.AddWarning(f'Não foi possível ajustar a tabela: {e}')


def _desligar_rotulos_camada(layer) -> None:
    """Garante que a camada de segmentos não rotule (só o traço).

    O ``CONFRONTANTES.lyrx`` liga Maplex com callout/cápsula; se restar
    ativo, a prancha ignora as camadas auxiliares deslocadas.
    """
    try:
        layer.showLabels = False
    except Exception:
        pass
    try:
        cim = layer.getDefinition('V3')
        for label_class in getattr(cim, 'labelClasses', []) or []:
            _definir(label_class, 'visibility', False)
        layer.setDefinition(cim)
        layer.showLabels = False
    except Exception as exc:
        arcpy.AddWarning(
            f'Não foi possível desligar rótulos da camada de segmentos: {exc}'
        )


def _remover_contorno_texto(simbolo_texto) -> None:
    """Sem callout (cápsula) e sem halo branco."""
    _definir(simbolo_texto, 'callout', None)
    _definir(simbolo_texto, 'haloSize', 0)
    try:
        simbolo_texto.haloSymbol = None
    except Exception:
        pass


def _configurar_empilhamento_rotulo(placement) -> None:
    """Permite quebra de linha no Maplex (espaço como separador)."""
    _definir(placement, 'canStackLabel', True)
    try:
        stacking = getattr(placement, 'labelStackingProperties', None)
        if stacking is None:
            stacking = arcpy.cim.CreateCIMObjectFromClassName(
                'CIMMaplexLabelStackingProperties', 'V3'
            )
        _definir(stacking, 'maximumNumberOfLines', 3)
        _definir(stacking, 'maximumNumberOfCharsPerLine', 24)
        _definir(stacking, 'minimumNumberOfCharsPerLine', 3)
        separador = arcpy.cim.CreateCIMObjectFromClassName(
            'CIMMaplexStackingSeparator', 'V3'
        )
        _definir(separador, 'separator', ' ')
        _definir(separador, 'splitAfter', True)
        _definir(stacking, 'separators', [separador])
        _definir(placement, 'labelStackingProperties', stacking)
    except Exception as exc:
        arcpy.AddWarning(f'Empilhamento de rótulo não configurado: {exc}')


def _configurar_rotulos_institucional(
    layer, rotulos_pontuais=False, lado_externo=None
):
    """Rótulos fora do perímetro, sem contorno textual."""
    try:
        cim = layer.getDefinition('V3')
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível ler a camada de rótulos: {exc}')
        return

    _ocultar_simbolo_da_camada(cim)

    classes = list(getattr(cim, 'labelClasses', []) or [])
    if not classes:
        try:
            classe = arcpy.cim.CreateCIMObjectFromClassName(
                'CIMLabelClass', 'V3'
            )
            classes = [classe]
            cim.labelClasses = classes
        except Exception as exc:
            arcpy.AddWarning(f'Sem classe de rótulo na camada: {exc}')
            return

    for label_class in classes:
        _definir(label_class, 'expression', '$feature.confrontante')
        _definir(label_class, 'expressionEngine', 'Arcade')
        _definir(label_class, 'visibility', True)
        placement = getattr(label_class, 'maplexLabelPlacementProperties', None)
        _configurar_empilhamento_rotulo(placement)
        _definir(placement, 'canOverrunFeature', True)
        _definir(placement, 'canRemoveOverlappingLabel', False)
        _definir(placement, 'removeAmbiguousLabels', 'None')
        _definir(placement, 'thinDuplicateLabels', False)
        _definir(placement, 'repeatLabel', False)
        _definir(placement, 'primaryOffsetUnit', 'Point')
        _definir(placement, 'multiPartOption', 'OneLabelPerFeature')
        if rotulos_pontuais:
            _definir(placement, 'featureType', 'Point')
            _definir(placement, 'pointPlacementMethod', 'AroundPoint')
            _definir(placement, 'preferHorizontalPlacement', True)
            _definir(placement, 'primaryOffset', 0)
        else:
            _definir(placement, 'featureType', 'Line')
            _definir(placement, 'linePlacementMethod', 'OffsetStraightFromLine')
            _definir(placement, 'alignLabelToLineDirection', True)
            _definir(placement, 'maximumLabelOverrun', 60)
            _definir(placement, 'maximumLabelOverrunUnit', 'Point')
            # Folga no papel; o lado (esq/dir) vem das classes por frente.
            _definir(placement, 'primaryOffset', AFASTAMENTO_ROTULO_LINHA_PT)

        standard = getattr(label_class, 'standardLabelPlacementProperties', None)
        _definir(standard, 'numLabelsOption', 'OneLabelPerFeature')

        referencia_texto = getattr(label_class, 'textSymbol', None)
        simbolo_texto = getattr(referencia_texto, 'symbol', None)
        if simbolo_texto is not None:
            _definir(simbolo_texto, 'height', ALTURA_TEXTO_ROTULO_PT)
            _remover_contorno_texto(simbolo_texto)

    if (not rotulos_pontuais) and classes:
        try:
            cim.labelClasses = _classes_por_lado(classes[0])
            for label_class in cim.labelClasses:
                referencia_texto = getattr(label_class, 'textSymbol', None)
                simbolo_texto = getattr(referencia_texto, 'symbol', None)
                if simbolo_texto is not None:
                    _remover_contorno_texto(simbolo_texto)
        except Exception as exc:
            raise RuntimeError(
                'Não foi possível prender o rótulo ao lado de fora da '
                f'divisa: {exc}'
            ) from exc

    if rotulos_pontuais and classes:
        try:
            cim.labelClasses = _classes_por_direcao(classes[0])
            for label_class in cim.labelClasses:
                referencia_texto = getattr(label_class, 'textSymbol', None)
                simbolo_texto = getattr(referencia_texto, 'symbol', None)
                if simbolo_texto is not None:
                    _remover_contorno_texto(simbolo_texto)
        except Exception as exc:
            arcpy.AddWarning(
                f'Classes por direção dos rótulos curtos falharam: {exc}'
            )

    try:
        layer.setDefinition(cim)
        layer.showLabels = True
    except Exception as exc:
        raise RuntimeError(
            f'Não foi possível aplicar rótulos institucionais: {exc}'
        ) from exc

    # Confirma que o ArcGIS preservou as propriedades críticas. A emissão não
    # pode seguir silenciosamente com OffsetCurved ou callout herdado.
    aplicado = layer.getDefinition('V3')
    problemas = []
    for classe in list(getattr(aplicado, 'labelClasses', []) or []):
        placement = getattr(classe, 'maplexLabelPlacementProperties', None)
        if not rotulos_pontuais:
            metodo = getattr(placement, 'linePlacementMethod', None)
            if metodo != 'OffsetStraightFromLine':
                problemas.append(f'linePlacementMethod={metodo!r}')
            lado = getattr(placement, 'constrainOffset', None)
            if lado not in ('LeftOfLine', 'RightOfLine'):
                problemas.append(f'constrainOffset={lado!r}')
        referencia = getattr(classe, 'textSymbol', None)
        simbolo = getattr(referencia, 'symbol', None)
        if simbolo is not None and getattr(simbolo, 'callout', None) is not None:
            problemas.append('callout residual')
    if problemas:
        raise RuntimeError(
            'Configuração CIM de rótulos não foi preservada: '
            + '; '.join(sorted(set(problemas)))
        )


def _aplicar_rotulos_confrontantes(
    map_frame_planta, segmentos, poligono_lote, afastamento_externo_m
):
    """Linhas só desenham o traço; rótulos vêm das camadas agrupadas."""
    (
        feature_rotulos,
        pontos_rotulos_curtos,
        lado_externo,
    ) = _criar_camadas_rotulos_confrontantes(
        segmentos,
        poligono_lote,
        afastamento_externo_m=afastamento_externo_m,
        comprimento_minimo_linha_m=COMPRIMENTO_MINIMO_ROTULO_LINHA_LOTE_M,
        comprimento_max_ponto_m=COMPRIMENTO_MAX_ROTULO_PONTO_LOTE_M,
        distancia_minima_rotulos_m=DISTANCIA_MINIMA_ROTULOS_LOTE_M,
    )

    # Sem CONFRONTANTES.lyrx: evita callout/cápsula e OffsetCurved do template.
    layer_rotulos = _adicionar_camada(map_frame_planta, feature_rotulos, None)
    if layer_rotulos is not None:
        _configurar_rotulos_institucional(
            layer_rotulos, lado_externo=lado_externo
        )

    layer_curtos = _adicionar_camada(map_frame_planta, pontos_rotulos_curtos, None)
    if layer_curtos is not None:
        _configurar_rotulos_institucional(
            layer_curtos, rotulos_pontuais=True, lado_externo=lado_externo
        )


def exportar_lotes_quadra(
    lote_camada,
    numero_reurb_coletivo: str,
    quadra,
) -> os.PathLike:
    """Seleciona os lotes da mesma quadra para o overview."""
    try:
        quadra_sql = str(int(str(quadra).strip()))
    except ValueError:
        q = str(quadra).strip().replace("'", "''")
        quadra_sql = f"'{q}'"
    reurb = str(numero_reurb_coletivo).strip().replace("'", "''")
    where = f"n_coletivo = '{reurb}' AND quadra = {quadra_sql}"
    return arcpy.Select_analysis(
        in_features=lote_camada,
        out_feature_class=os.path.join(arcpy.env.scratchGDB, 'lotes_quadra_overview'),
        where_clause=where,
    )


def gerar_planta_institucional(
    lote_selecionado,
    confrontantes_lote,
    vertices_lote,
    lotes_quadra,
    interessado,
    bairro,
    municipio,
    denominacao,
    quadra,
    lote,
    area,
    perimetro,
    data,
    fusoutm,
    responsavel_tecnico,
    funcao,
    n_crea_cau,
    interessado_cpf=None,
):
    """Monta a folha A3 no layout de planta individual (gerarplantareurb)."""
    if not os.path.exists(projeto_arcgis):
        raise RuntimeError(
            f'Projeto ArcGIS não encontrado: {projeto_arcgis}. '
            'Copie o project_layout.aprx do gerarplantareurb.'
        )

    aprx = arcpy.mp.ArcGISProject(aprx_path=projeto_arcgis)
    mapas = aprx.listMaps()
    if len(mapas) < 2:
        raise RuntimeError(
            'project_layout.aprx precisa de MAP_FRAME e OVERVIEW_MAP_FRAME.'
        )
    map_frame_planta = mapas[0]
    map_overview_planta = mapas[1]

    layouts = [layout for layout in aprx.listLayouts() if layout.name == nome_layout_planta]
    if not layouts:
        layouts = aprx.listLayouts()
    if not layouts:
        raise RuntimeError('Nenhum layout encontrado no project_layout.aprx.')
    layout_planta = layouts[0]

    _adicionar_camada(map_frame_planta, lote_selecionado, simbologia_lote)

    layer_conf = _adicionar_camada(
        map_frame_planta, confrontantes_lote, simbologia_confrontantes
    )
    if layer_conf is not None:
        # Traço dos segmentos; rótulo sai das camadas auxiliares externas.
        _desligar_rotulos_camada(layer_conf)

    layer_vert = _adicionar_camada(map_frame_planta, vertices_lote, simbologia_vertices)
    if layer_vert is not None:
        _configurar_rotulos_vertices(layer_vert)

    # Define primeiro a escala final. O afastamento cartográfico é convertido
    # de milímetros no papel para metros no mapa, mantendo aparência constante.
    escala_principal = _ajustar_escala(
        map_frame_planta, layout_planta, lote_selecionado, 'MAP_FRAME'
    )
    afastamento_externo_m = afastamento_mapa_m(escala_principal)
    arcpy.AddMessage(
        f'Rótulos externos: escala 1:{int(escala_principal)}; '
        f'afastamento {DISTANCIA_ROTULO_EXTERNO_MM:g} mm '
        f'(= {afastamento_externo_m:.2f} m no mapa)'
    )

    try:
        _aplicar_rotulos_confrontantes(
            map_frame_planta,
            confrontantes_lote,
            lote_selecionado,
            afastamento_externo_m,
        )
    except Exception as e:
        raise RuntimeError(
            'Falha na configuração segura dos rótulos externos; '
            'a planta não será emitida com posicionamento incerto. '
            f'Detalhe: {e}'
        ) from e

    for camada, simbologia in (
        (lote_selecionado, simbologia_lote_overview),
        (lotes_quadra, simbologia_quadra_overview),
    ):
        _adicionar_camada(map_overview_planta, camada, simbologia)

    _ajustar_escala(
        map_overview_planta, layout_planta, lotes_quadra, 'OVERVIEW_MAP_FRAME'
    )

    _ajustar_textos(
        layout_planta=layout_planta,
        interessado=interessado,
        interessado_cpf=interessado_cpf,
        bairro=bairro,
        municipio=municipio,
        denominacao=denominacao,
        quadra=quadra,
        lote=lote,
        area=area,
        perimetro=perimetro,
        data=data,
        fusoutm=fusoutm,
        responsavel_tecnico=responsavel_tecnico,
        funcao=funcao,
        n_crea_cau=n_crea_cau,
    )
    _ajustar_tabela(layout_planta)
    return layout_planta, aprx


def exportar_planta_institucional_para_pdf(layout_planta, out_pdf):
    from exportar_pdf_unificado import exportar_pdf_layout

    return exportar_pdf_layout(layout_planta, out_pdf)
