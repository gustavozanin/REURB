# -*- coding: utf-8 -*-
"""Folha 1 (A3) da planta de perímetro: vértices, segmentos/confrontantes,
overview e basemap — SEM lotes/quadras (fora do escopo desta ferramenta,
ver `.specs/features/gerarplantaverticesconfrontantesmemorial/spec.md`).

Espelha os padrões de `gerarplantanucleo/gerarplantanucleo/gerar_planta.py`
(mesma forma de adicionar camada, ajustar escala, ajustar textos e
basemap com fallback), mas sem a tabela/lógica de quadras — o quadro de
coordenadas desta ferramenta vive em `quadro_coordenadas.py`, com layout
e Table Frame próprios.

O layout `Layout_Planta_Perimetro_A3` e os map frames `MAP_FRAME` /
`OVERVIEW_MAP_FRAME` são validados antes da montagem. O mesmo vale para
os elementos obrigatórios do carimbo, tabela e autenticação: uma prancha
incompleta nunca deve ser exportada como entrega válida.
"""

import copy
import math
import os

try:
    import arcpy
except ImportError:
    arcpy = None

from caminhos_gerais import projeto_arcgis
from caminhos_gerais import nome_layout_planta as NOME_LAYOUT_PLANTA
from caminho_simbologias import (
    simbologia_confrontantes,
    simbologia_vertices,
    simbologia_perimetro_overview,
)
from constantes import (
    LIMITE_RESUMO_TABELA_PLANTA,
    TEXTO_AVISO_TABELA_PLANTA,
    TEXTO_TABELA_COMPLETA_PLANTA,
)
from exportar_pdf_unificado import exportar_pdf_layout, planejar_folhas

NOME_MAPA_PRINCIPAL = 'MAP_FRAME'
NOME_MAPA_OVERVIEW = 'OVERVIEW_MAP_FRAME'
NOME_TABELA_PLANTA = 'tabela_dados'
CAMPOS_TABELA_PLANTA = [
    'de', 'para', 'azimute', 'distancia', 'E', 'N', 'confrontantes'
]
NOME_CAMADA_ROTULOS = 'rotulos_confrontantes_agrupados'
NOME_PONTOS_ROTULOS_CURTOS = 'rotulos_confrontantes_curtos'
# Abaixo disso o nome não cabe ao longo do traçado e vira rótulo pontual.
COMPRIMENTO_MINIMO_ROTULO_LINHA_M = 45

# Folga entre o ponto da frente e a caixa do texto, no papel. Em pontos
# (não em metros) para o afastamento não mudar com a escala da prancha.
AFASTAMENTO_ROTULO_CURTO_PT = 6

# Posições do Maplex por direção cardinal externa da frente (enum
# MaplexPointPlacementMethod, CIM v3). O método é propriedade da classe
# de rótulo, não da feição, então cada direção vira uma classe própria
# filtrada pelo campo `direcao` (ver `_classes_por_direcao`).
POSICOES_CARDINAIS = {
    'N': 'NorthOfPoint',
    'NE': 'NorthEastOfPoint',
    'E': 'EastOfPoint',
    'SE': 'SouthEastOfPoint',
    'S': 'SouthOfPoint',
    'SW': 'SouthWestOfPoint',
    'W': 'WestOfPoint',
    'NW': 'NorthWestOfPoint',
}
# Dois rótulos do mesmo confrontante mais próximos que isto (medido ao
# longo do perímetro) viram repetição espremida: fica só o trecho maior.
DISTANCIA_MINIMA_ENTRE_ROTULOS_M = 200
ALTURA_TEXTO_ROTULO_PT = 7.5
HALO_TEXTO_ROTULO_PT = 1.5
AFASTAMENTO_ROTULO_LINHA_PT = 6
TEXTO_MATRICULA_VAZIA = '—'

ELEMENTOS_TEXTO_OBRIGATORIOS = (
    '{bairro}', '{municipio}', '{area}', '{processo}', '{perimetro}',
    '{data}', '{fusoutm}', '{responsavel_tecnico}', '{funcao}',
    '{n_crea_cau}', '{matricula}', '{folha}', '{protocolo}',
    '{aviso_tabela}',
)
# Serviço público de imagens de satélite (igual Núcleo/Loteamento); o
# basemap local/portal pode não ter "Imagery" disponível.
BASEMAP_WORLD_IMAGERY_URL = (
    r'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
)

MENSAGEM_APRX_AUSENTE = (
    'Projeto ArcGIS "{caminho}" não encontrado. Os layouts desta ferramenta '
    'precisam ser configurados no ArcGIS Pro — ver instruções em '
    'layout/LEIA-ME_LAYOUTS.txt antes de gerar a planta de perímetro.'
)
MENSAGEM_LAYOUT_AUSENTE = (
    'Layout "{layout}" não encontrado em "{caminho}". Confira se os 3 '
    'layouts foram criados com os nomes exatos indicados em '
    'layout/LEIA-ME_LAYOUTS.txt.'
)
MENSAGEM_MAPA_AUSENTE = (
    'Mapa "{mapa}" não encontrado em "{caminho}". Confira os nomes dos map '
    'frames indicados em layout/LEIA-ME_LAYOUTS.txt.'
)


class LayoutConfigurationError(RuntimeError):
    """Indica configuração ausente no APRX, distinta de falha operacional."""


def validar_elementos_layout(layout):
    """Falha cedo quando a prancha não possui todos os elementos contratuais."""
    faltantes = []
    for nome in ELEMENTOS_TEXTO_OBRIGATORIOS:
        if not layout.listElements('TEXT_ELEMENT', nome):
            faltantes.append(f'TEXT_ELEMENT {nome}')
    if not layout.listElements('TABLEFRAME_ELEMENT', NOME_TABELA_PLANTA):
        faltantes.append(f'TABLEFRAME_ELEMENT {NOME_TABELA_PLANTA}')
    for nome in (NOME_MAPA_PRINCIPAL, NOME_MAPA_OVERVIEW):
        if not layout.listElements('MAPFRAME_ELEMENT', nome):
            faltantes.append(f'MAPFRAME_ELEMENT {nome}')
    if faltantes:
        raise LayoutConfigurationError(
            'Layout A3 incompleto; elementos obrigatórios ausentes: '
            + ', '.join(faltantes)
            + '. Corrija layout/project_layout.aprx antes de gerar o PDF.'
        )
    return True


def _numero_vertice(nome):
    try:
        return int(str(nome).split('-')[-1])
    except (TypeError, ValueError):
        return 0


def _agrupar_segmentos_consecutivos(registros):
    """Agrupa sequências contíguas sem modificar os segmentos publicados."""
    ordenados = sorted(registros, key=lambda item: _numero_vertice(item['de']))
    grupos = []
    for registro in ordenados:
        confrontante = str(registro.get('confrontante') or '').strip()
        registro = dict(registro, confrontante=confrontante)
        if grupos and grupos[-1][0]['confrontante'] == confrontante:
            grupos[-1].append(registro)
        else:
            grupos.append([registro])

    # O fechamento P-n -> P-001 também é uma continuidade válida.
    if (
        len(grupos) > 1
        and grupos[0][0]['confrontante'] == grupos[-1][0]['confrontante']
    ):
        grupos[0] = grupos[-1] + grupos[0]
        grupos.pop()
    return grupos


def orientacao_anel(pontos_xy):
    """Sentido do anel pela área assinada: 1 anti-horário, -1 horário.

    Args:
        pontos_xy: sequência de pares (x, y) na ordem do anel.

    Returns:
        int: 1 (anti-horário), -1 (horário) ou 0 (indefinido).
    """
    if len(pontos_xy) < 3:
        return 0
    soma = 0.0
    total = len(pontos_xy)
    for i in range(total):
        x1, y1 = pontos_xy[i]
        x2, y2 = pontos_xy[(i + 1) % total]
        soma += x1 * y2 - x2 * y1
    if soma > 0:
        return 1
    if soma < 0:
        return -1
    return 0


def lado_externo_do_rotulo(sentido):
    """Lado da linha que fica fora do polígono, no vocabulário do Maplex.

    Em anel anti-horário o interior fica à esquerda do sentido de
    digitalização, então o rótulo vai para a direita (e vice-versa).
    """
    if sentido > 0:
        return 'RightOfLine'
    if sentido < 0:
        return 'LeftOfLine'
    return 'NoConstraint'


def codigo_cardinal(dx, dy):
    """
    Direção cardinal de um vetor, em setores de 45°.

    Usada para escolher de que lado do ponto o Maplex escreve o nome do
    confrontante: o vetor informado é a normal que aponta para fora do
    perímetro. Y cresce para o norte, como nas coordenadas de mapa (e ao
    contrário das coordenadas de página).

    Args:
        dx: componente leste-oeste do vetor.
        dy: componente norte-sul do vetor.

    Returns:
        str: uma das chaves de `POSICOES_CARDINAIS`; 'E' para vetor nulo.
    """
    if not dx and not dy:
        return 'E'
    setor = int(((math.degrees(math.atan2(dy, dx)) + 382.5) % 360) // 45)
    return ('E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE')[setor]


def selecionar_grupos_rotulaveis(grupos_resumo, distancia_minima_m=None):
    """Evita repetir o mesmo confrontante em rótulos espremidos.

    Uma via longa deve ter o nome repetido ao longo da frente, mas dois
    rótulos iguais quase colados (caso típico de frente partida por uma
    travessa curta) poluem a prancha. Mantém sempre o trecho mais longo
    e descarta os do mesmo nome que ficariam perto dele, medindo a
    distância ao longo do próprio perímetro.

    Args:
        grupos_resumo: lista de dicts com `confrontante` e `comprimento`,
            na ordem do anel.
        distancia_minima_m: separação mínima entre dois rótulos de mesmo
            confrontante.

    Returns:
        list[bool]: para cada grupo, se ele deve receber rótulo.
    """
    if distancia_minima_m is None:
        distancia_minima_m = DISTANCIA_MINIMA_ENTRE_ROTULOS_M

    total = len(grupos_resumo)
    if total <= 1:
        return [True] * total

    nomes = [str(g.get('confrontante') or '').strip() for g in grupos_resumo]
    comprimentos = []
    for grupo in grupos_resumo:
        try:
            comprimentos.append(float(grupo.get('comprimento') or 0))
        except (TypeError, ValueError):
            comprimentos.append(0.0)

    perimetro = sum(comprimentos)
    centros = []
    acumulado = 0.0
    for comprimento in comprimentos:
        centros.append(acumulado + comprimento / 2)
        acumulado += comprimento

    def distancia_no_anel(i, j):
        bruta = abs(centros[i] - centros[j])
        return min(bruta, perimetro - bruta) if perimetro else bruta

    escolhidos = []
    for indice in sorted(range(total), key=lambda i: -comprimentos[i]):
        conflita = any(
            nomes[indice] == nomes[aceito]
            and distancia_no_anel(indice, aceito) < distancia_minima_m
            for aceito in escolhidos
        )
        if not conflita:
            escolhidos.append(indice)

    aceitos = set(escolhidos)
    return [i in aceitos for i in range(total)]


def _pontos_da_geometria(geometry):
    pontos = []
    for parte in geometry:
        for ponto in parte:
            if ponto is not None:
                pontos.append(arcpy.Point(ponto.X, ponto.Y))
    return pontos


def _normal_externa(linha, anel, centroide):
    """
    Vetor unitário que sai do meio da frente para fora do perímetro.

    Usa a perpendicular à própria frente e decide o lado sondando o anel
    com `contains`. A direção "do centroide para a frente", usada antes,
    aponta para dentro nas reentrâncias de contornos irregulares, e era
    o que jogava rótulos de rua para dentro da área.

    Args:
        linha: `arcpy.Polyline` da frente.
        anel: `arcpy.Polygon` do perímetro rotulado, ou None.
        centroide: ponto central do perímetro, usado como alternativa
            quando o anel não pode ser construído.

    Returns:
        tuple: componentes (dx, dy) do vetor unitário.
    """
    meio = linha.positionAlongLine(0.5, True).firstPoint
    antes = linha.positionAlongLine(0.45, True).firstPoint
    depois = linha.positionAlongLine(0.55, True).firstPoint
    tx, ty = depois.X - antes.X, depois.Y - antes.Y
    modulo = math.hypot(tx, ty)
    if not modulo:
        dx, dy = meio.X - centroide.X, meio.Y - centroide.Y
        distancia = math.hypot(dx, dy) or 1.0
        return dx / distancia, dy / distancia

    nx, ny = -ty / modulo, tx / modulo
    if anel is not None:
        # Sonda curta: em frentes estreitas um passo longo atravessaria o
        # perímetro e daria o lado errado.
        passo = min(5.0, max(0.5, linha.length * 0.1))
        sonda = arcpy.PointGeometry(
            arcpy.Point(meio.X + nx * passo, meio.Y + ny * passo),
            anel.spatialReference,
        )
        try:
            if anel.contains(sonda):
                nx, ny = -nx, -ny
            return nx, ny
        except Exception as exc:
            arcpy.AddWarning(
                f'Lado externo do rótulo pela geometria falhou: {exc}'
            )

    # Sem anel confiável, mantém o critério antigo (centroide -> frente),
    # que acerta o lado em contornos convexos.
    for candidato in ((nx, ny), (-nx, -ny)):
        if (
            candidato[0] * (meio.X - centroide.X)
            + candidato[1] * (meio.Y - centroide.Y)
        ) > 0:
            return candidato
    return nx, ny


def _anel_do_perimetro(pontos_anel, sr):
    """Polígono do contorno rotulado, para decidir o lado externo.

    Vem dos próprios pontos das frentes, e não da feição do bairro, para
    não depender do tipo de geometria nem de eventuais ilhas.
    """
    if len(pontos_anel) < 3:
        return None
    try:
        return arcpy.Polygon(
            arcpy.Array([arcpy.Point(x, y) for x, y in pontos_anel]), sr
        )
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível montar o anel do perímetro: {exc}')
        return None


def _criar_camadas_rotulos_confrontantes(feature, feicao_perimetro):
    """Cria as feições auxiliares de rótulo de confrontante.

    Agrupa segmentos consecutivos do mesmo confrontante, mantém um único
    rótulo por frente (ver `selecionar_grupos_rotulaveis`) e separa as
    frentes curtas em pontos, cada um com a direção cardinal que aponta
    para fora do perímetro (campo `direcao`, ver `_normal_externa`).

    Returns:
        tuple: `(linhas, pontos, lado_externo)` — feição de linhas, feição
        de pontos das frentes curtas e o lado do Maplex que fica fora do
        polígono.
    """
    sr = arcpy.Describe(feature).spatialReference
    with arcpy.da.SearchCursor(feicao_perimetro, ['SHAPE@']) as cursor:
        centroide = next(cursor)[0].trueCentroid
    out_fc = os.path.join(arcpy.env.scratchGDB, NOME_CAMADA_ROTULOS)
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)
    arcpy.management.CreateFeatureclass(
        arcpy.env.scratchGDB,
        NOME_CAMADA_ROTULOS,
        'POLYLINE',
        spatial_reference=sr,
    )
    arcpy.management.AddFields(
        out_fc,
        [
            ['confrontante', 'TEXT', 'Confrontante', 255],
            ['qtd_trechos', 'LONG', 'Quantidade de trechos'],
            ['comprimento', 'DOUBLE', 'Comprimento (m)'],
        ],
    )
    out_points = os.path.join(
        arcpy.env.scratchGDB, NOME_PONTOS_ROTULOS_CURTOS
    )
    if arcpy.Exists(out_points):
        arcpy.management.Delete(out_points)
    arcpy.management.CreateFeatureclass(
        arcpy.env.scratchGDB,
        NOME_PONTOS_ROTULOS_CURTOS,
        'POINT',
        spatial_reference=sr,
    )
    arcpy.management.AddFields(
        out_points,
        [
            ['confrontante', 'TEXT', 'Confrontante', 255],
            ['comprimento', 'DOUBLE', 'Comprimento (m)'],
            ['direcao', 'TEXT', 'Direção externa', 2],
        ],
    )

    registros = []
    with arcpy.da.SearchCursor(
        feature, ['SHAPE@', 'de', 'para', 'confrontantes']
    ) as cursor:
        for geometry, de, para, confrontante in cursor:
            registros.append(
                {
                    'geometry': geometry,
                    'de': de,
                    'para': para,
                    'confrontante': confrontante,
                }
            )

    grupos = _agrupar_segmentos_consecutivos(registros)
    linhas_grupos = []
    pontos_anel = []
    for grupo in grupos:
        pontos = []
        for registro in grupo:
            segmento = _pontos_da_geometria(registro['geometry'])
            if pontos and segmento:
                if (
                    abs(pontos[-1].X - segmento[0].X) < 0.001
                    and abs(pontos[-1].Y - segmento[0].Y) < 0.001
                ):
                    segmento = segmento[1:]
            pontos.extend(segmento)
        linha = arcpy.Polyline(arcpy.Array(pontos), sr)
        linhas_grupos.append((linha, grupo))
        pontos_anel.extend((p.X, p.Y) for p in pontos)

    lado_externo = lado_externo_do_rotulo(orientacao_anel(pontos_anel))

    resumo = [
        {'confrontante': grupo[0]['confrontante'], 'comprimento': linha.length}
        for linha, grupo in linhas_grupos
    ]
    rotulaveis = selecionar_grupos_rotulaveis(resumo)
    suprimidos = sum(1 for marca in rotulaveis if not marca)
    if suprimidos:
        arcpy.AddMessage(
            f'Rótulos de confrontante unificados por frente: '
            f'{suprimidos} repetição(ões) suprimida(s).'
        )

    with arcpy.da.InsertCursor(
        out_fc, ['SHAPE@', 'confrontante', 'qtd_trechos', 'comprimento']
    ) as cursor:
        for indice, (linha, grupo) in enumerate(linhas_grupos):
            if not rotulaveis[indice]:
                continue
            cursor.insertRow(
                [
                    linha,
                    grupo[0]['confrontante'],
                    len(grupo),
                    linha.length,
                ]
            )
    anel = _anel_do_perimetro(pontos_anel, sr)
    with arcpy.da.InsertCursor(
        out_points, ['SHAPE@', 'confrontante', 'comprimento', 'direcao']
    ) as cursor:
        for indice, (linha, grupo) in enumerate(linhas_grupos):
            if not rotulaveis[indice]:
                continue
            if linha.length < COMPRIMENTO_MINIMO_ROTULO_LINHA_M:
                normal = _normal_externa(linha, anel, centroide)
                meio = linha.positionAlongLine(0.5, True).firstPoint
                cursor.insertRow(
                    [
                        arcpy.PointGeometry(arcpy.Point(meio.X, meio.Y), sr),
                        grupo[0]['confrontante'],
                        linha.length,
                        codigo_cardinal(*normal),
                    ]
                )
    return out_fc, out_points, lado_externo


def _obter_projeto():
    """Abre o `project_layout.aprx` desta ferramenta, com erro claro se ausente."""
    if arcpy is None:
        raise LayoutConfigurationError('arcpy não disponível neste ambiente.')
    if not os.path.exists(projeto_arcgis):
        raise LayoutConfigurationError(MENSAGEM_APRX_AUSENTE.format(caminho=projeto_arcgis))
    return arcpy.mp.ArcGISProject(projeto_arcgis)


def _obter_layout(aprx, nome):
    for layout in aprx.listLayouts():
        if layout.name == nome:
            return layout
    raise LayoutConfigurationError(MENSAGEM_LAYOUT_AUSENTE.format(layout=nome, caminho=projeto_arcgis))


def _obter_mapa(aprx, nome):
    for mapa in aprx.listMaps():
        if mapa.name == nome:
            return mapa
    raise LayoutConfigurationError(MENSAGEM_MAPA_AUSENTE.format(mapa=nome, caminho=projeto_arcgis))


def _adicionar_camada(aprx_map, feature, simbologia):
    """Adiciona uma camada ao map frame ou overview (aviso, não erro, se a simbologia faltar)."""
    arcpy.AddMessage(f'Adicionando a camada: {feature}')

    if simbologia and not os.path.exists(simbologia):
        arcpy.AddWarning(f'Arquivo de simbologia não encontrado: {simbologia}')

    if not int(arcpy.management.GetCount(feature)[0]):
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
            arcpy.AddWarning(f'Erro ao aplicar simbologia: {str(e)}')

    # Garante rótulos na prancha (confrontantes/vértices), mesmo se o
    # .lyrx vier com labelVisibility desligado em alguma cópia do pacote.
    try:
        if hasattr(layer, 'showLabels'):
            layer.showLabels = True
    except Exception as e:
        arcpy.AddWarning(f'Não foi possível ligar rótulos em {feature}: {e}')

    return layer


def _ocultar_campos_internos(layer):
    """Impede que campos de sistema apareçam no Table Frame da planta."""
    try:
        cim = layer.getDefinition('V3')
        feature_table = getattr(cim, 'featureTable', None)
        for field in getattr(feature_table, 'fieldDescriptions', []) or []:
            if field.fieldName.lower() in {
                'objectid', 'shape', 'shape_length', 'shape_leng'
            }:
                field.visible = False
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(
            f'Não foi possível ocultar campos internos da tabela: {exc}'
        )


def _definir(objeto, nome, valor):
    """Atribui uma propriedade CIM sem derrubar o restante da configuração."""
    if objeto is None:
        return
    try:
        setattr(objeto, nome, valor)
    except Exception as exc:
        arcpy.AddWarning(f'Propriedade de rótulo "{nome}" ignorada: {exc}')


def _ocultar_simbolo_da_camada(cim):
    """Remove o desenho da feição auxiliar, preservando os rótulos."""
    renderer = getattr(cim, 'renderer', None)
    referencia = getattr(renderer, 'symbol', None)
    simbolo = getattr(referencia, 'symbol', None)
    if simbolo is None:
        return False
    try:
        simbolo.symbolLayers = []
        return True
    except Exception as exc:
        arcpy.AddWarning(
            f'Não foi possível remover o símbolo da camada de rótulos: {exc}'
        )
        return False


def _aplicar_halo_branco(simbolo_texto):
    """Halo branco no texto (o `.lyrx` traz haloSize sem símbolo de halo)."""
    _definir(simbolo_texto, 'haloSize', HALO_TEXTO_ROTULO_PT)
    if getattr(simbolo_texto, 'haloSymbol', None) is not None:
        return
    try:
        halo = arcpy.cim.CreateCIMObjectFromClassName('CIMPolygonSymbol', 'V3')
        preenchimento = arcpy.cim.CreateCIMObjectFromClassName(
            'CIMSolidFill', 'V3'
        )
        cor = arcpy.cim.CreateCIMObjectFromClassName('CIMRGBColor', 'V3')
        cor.values = [255, 255, 255, 100]
        preenchimento.color = cor
        halo.symbolLayers = [preenchimento]
        simbolo_texto.haloSymbol = halo
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível criar o halo do rótulo: {exc}')


def _configurar_classe_rotulo(label_class, rotulos_pontuais, lado_externo):
    """Aplica a uma classe de rótulo o padrão de confrontante da prancha."""
    _definir(label_class, 'expression', '$feature.confrontante')
    _definir(label_class, 'expressionEngine', 'Arcade')
    placement = getattr(label_class, 'maplexLabelPlacementProperties', None)
    _definir(placement, 'canStackLabel', False)
    _definir(placement, 'canOverrunFeature', True)
    # Confrontante é informação obrigatória: não some por sobreposição.
    _definir(placement, 'canRemoveOverlappingLabel', False)
    _definir(placement, 'removeAmbiguousLabels', 'None')
    _definir(placement, 'thinDuplicateLabels', False)
    _definir(placement, 'repeatLabel', False)
    _definir(placement, 'fontHeightReductionLimit', 6)
    _definir(placement, 'fontWidthReductionLimit', 90)
    _definir(placement, 'labelBuffer', 2)
    _definir(placement, 'primaryOffsetUnit', 'Point')
    _definir(placement, 'maximumLabelOverrun', 48)
    _definir(placement, 'maximumLabelOverrunUnit', 'Point')
    _definir(placement, 'multiPartOption', 'OneLabelPerFeature')
    if rotulos_pontuais:
        _definir(placement, 'featureType', 'Point')
        # Alternativa caso as classes por direção não possam ser criadas.
        _definir(placement, 'pointPlacementMethod', 'AroundPoint')
        _definir(placement, 'preferHorizontalPlacement', True)
        _definir(placement, 'primaryOffset', AFASTAMENTO_ROTULO_CURTO_PT)
    else:
        _definir(placement, 'featureType', 'Line')
        # Reto acompanha a direção da frente sem serpentear como o curvo.
        _definir(placement, 'linePlacementMethod', 'OffsetStraightFromLine')
        # False impede o nome sair de cabeça para baixo.
        _definir(placement, 'alignLabelToLineDirection', False)
        _definir(placement, 'primaryOffset', AFASTAMENTO_ROTULO_LINHA_PT)
        if lado_externo and lado_externo != 'NoConstraint':
            _definir(placement, 'constrainOffset', lado_externo)

    standard = getattr(label_class, 'standardLabelPlacementProperties', None)
    _definir(standard, 'numLabelsOption', 'OneLabelPerFeature')

    referencia_texto = getattr(label_class, 'textSymbol', None)
    simbolo_texto = getattr(referencia_texto, 'symbol', None)
    if simbolo_texto is not None:
        _definir(simbolo_texto, 'height', ALTURA_TEXTO_ROTULO_PT)
        # O .lyrx traz um callout composto que desenha "cápsula"
        # em volta do texto — fora do padrão da planta.
        _definir(simbolo_texto, 'callout', None)
        _aplicar_halo_branco(simbolo_texto)


def _classes_por_direcao(modelo):
    """
    Uma classe de rótulo por direção cardinal externa da frente.

    O método de posicionamento é propriedade da classe de rótulo, e não
    da feição, então prender o texto do lado de fora frente a frente
    exige uma classe por direção, filtrada pelo campo `direcao` gravado
    em `_criar_camadas_rotulos_confrontantes`.

    Cada classe só escreve as frentes da direção dela, e devolve texto
    vazio nas outras (rótulo vazio não é desenhado). O filtro fica na
    expressão, e não em `whereClause`, porque a expressão já é o caminho
    usado nesta camada: se um `whereClause` fosse ignorado pelo CIM, as
    oito classes rotulariam todas as frentes de uma vez.

    Args:
        modelo: classe de rótulo já configurada, usada como base.

    Returns:
        list: uma classe por entrada de `POSICOES_CARDINAIS`.
    """
    classes = []
    for codigo, metodo in POSICOES_CARDINAIS.items():
        condicao = f"$feature.direcao == '{codigo}'"
        if codigo == 'E':
            # Direção sem valor não pode ficar sem rótulo: cai no leste.
            condicao = f'(IsEmpty($feature.direcao) || {condicao})'
        clone = copy.deepcopy(modelo)
        _definir(clone, 'name', f'confrontante_{codigo}')
        _definir(
            clone,
            'expression',
            f"IIf({condicao}, $feature.confrontante, '')",
        )
        _definir(clone, 'expressionEngine', 'Arcade')
        _definir(clone, 'visibility', True)
        placement = getattr(clone, 'maplexLabelPlacementProperties', None)
        _definir(placement, 'pointPlacementMethod', metodo)
        classes.append(clone)
    return classes


def _configurar_camada_rotulos(
    layer, rotulos_pontuais=False, lado_externo=None
):
    """Deixa a camada invisível e mantém apenas rótulos cartográficos."""
    try:
        cim = layer.getDefinition('V3')
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível ler a camada de rótulos: {exc}')
        return

    simbolo_oculto = _ocultar_simbolo_da_camada(cim)

    classes = list(getattr(cim, 'labelClasses', []) or [])
    for label_class in classes:
        _configurar_classe_rotulo(label_class, rotulos_pontuais, lado_externo)

    if rotulos_pontuais and classes:
        try:
            cim.labelClasses = _classes_por_direcao(classes[0])
        except Exception as exc:
            arcpy.AddWarning(
                'Não foi possível criar uma classe de rótulo por direção '
                f'({exc}); os rótulos das frentes curtas ficam com '
                'posicionamento livre em volta do ponto.'
            )

    try:
        layer.setDefinition(cim)
        layer.showLabels = True
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível aplicar os rótulos: {exc}')

    if simbolo_oculto:
        return

    # Fallback só depois do setDefinition, senão a definição antiga volta.
    try:
        symbology = layer.symbology
        simbolo = getattr(getattr(symbology, 'renderer', None), 'symbol', None)
        if simbolo is not None:
            simbolo.color = {'RGB': [0, 0, 0, 0]}
            layer.symbology = symbology
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível ocultar o símbolo auxiliar: {exc}')


def _configurar_rotulos_vertices(layer):
    """Garante que nenhum vértice P-xxx suma por conflito Maplex."""
    try:
        if hasattr(layer, 'showLabels'):
            layer.showLabels = True
        cim = layer.getDefinition('V3')
        for label_class in getattr(cim, 'labelClasses', []) or []:
            placement = label_class.maplexLabelPlacementProperties
            placement.canRemoveOverlappingLabel = False
            placement.canStackLabel = False
            placement.removeAmbiguousLabels = 'None'
            placement.fontHeightReductionLimit = 5
            placement.primaryOffset = 4
            placement.primaryOffsetUnit = 'Point'
            text_symbol = getattr(label_class, 'textSymbol', None)
            symbol = getattr(text_symbol, 'symbol', None)
            if symbol is not None:
                if getattr(symbol, 'height', 10) > 7:
                    symbol.height = 7
                symbol.haloSize = max(getattr(symbol, 'haloSize', 0) or 0, 1.25)
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(
            f'Não foi possível reforçar rótulos dos vértices: {exc}'
        )


def _configurar_tabela_planta(layout, aprx_map, feature, layer_fallback, tem_anexo):
    """Vincula a tabela sem limitar a camada desenhada no mapa.

    Só corta a lista em `LIMITE_RESUMO_TABELA_PLANTA` quando o Quadro
    completo vai em folha adicional; cabendo tudo, a tabela sai integral.
    """
    tabelas = layout.listElements(
        'TABLEFRAME_ELEMENT', NOME_TABELA_PLANTA
    )
    if not tabelas:
        arcpy.AddWarning(
            f'Table Frame "{NOME_TABELA_PLANTA}" não encontrado no layout.'
        )
        return
    tabela = tabelas[0]
    fonte_tabela = layer_fallback
    try:
        fonte_tabela = aprx_map.addDataFromPath(feature)
        fonte_tabela.name = 'resumo_segmentos_planta'
        if tem_anexo:
            fonte_tabela.definitionQuery = (
                f"de <= '{LIMITE_RESUMO_TABELA_PLANTA}'"
            )
        fonte_tabela.visible = False
        _ocultar_campos_internos(fonte_tabela)
    except Exception as exc:
        arcpy.AddWarning(
            f'Não foi possível limitar a tabela-resumo a '
            f'{LIMITE_RESUMO_TABELA_PLANTA}: {exc}'
        )
    tabela.table = fonte_tabela
    tabela.fields = CAMPOS_TABELA_PLANTA
    cim = tabela.getDefinition('V3')
    cim.columns = 1
    cim.balanceColumns = False
    tabela.setDefinition(cim)


def _contar_segmentos(feature):
    """Conta feições da camada de segmentos; 0 se a contagem falhar."""
    try:
        return int(arcpy.GetCount_management(feature).getOutput(0))
    except Exception as exc:
        arcpy.AddWarning(f'Não foi possível contar os segmentos: {exc}')
        return 0


def _preencher_aviso_tabela(layout, plano_folhas):
    """Preenche o aviso da tabela conforme haja ou não folha adicional."""
    if plano_folhas['tem_anexo']:
        texto = TEXTO_AVISO_TABELA_PLANTA.format(
            limite=LIMITE_RESUMO_TABELA_PLANTA,
            folha_quadro=plano_folhas['folha_quadro'],
        )
    else:
        texto = TEXTO_TABELA_COMPLETA_PLANTA
    for nome in ('{aviso_tabela}', 'aviso_tabela'):
        elementos = layout.listElements(
            element_type='TEXT_ELEMENT', wildcard=nome
        )
        if elementos:
            elementos[0].text = texto
            return
    arcpy.AddWarning(
        'Elemento de texto do aviso da tabela '
        '("{aviso_tabela}" ou "aviso_tabela") não encontrado no layout. '
        'Inclua o TextElement no Layout_Planta_Perimetro_A3 para exibir: '
        f'{texto}'
    )


def _adicionar_basemap_imagery(aprx_map):
    """Adiciona o basemap World Imagery público; segue sem ele se falhar (igual Loteamento)."""
    try:
        aprx_map.addDataFromPath(BASEMAP_WORLD_IMAGERY_URL)
    except Exception as e:
        arcpy.AddWarning(
            f'Não foi possível adicionar imagem de satélite no overview ({e}). '
            'Continuando sem basemap.'
        )


def _ajustar_escala_visualizacao(aprx_map, layout, feature_extent, element_wildcard):
    """Ajusta a escala do map frame ao extent do perímetro (mesmo cálculo do Núcleo)."""
    extent = arcpy.Describe(feature_extent).extent
    map_frames = layout.listElements(
        element_type='MAPFRAME_ELEMENT', wildcard=element_wildcard
    )
    if not map_frames:
        raise LayoutConfigurationError(
            MENSAGEM_MAPA_AUSENTE.format(mapa=element_wildcard, caminho=projeto_arcgis)
        )

    map_frame = map_frames[0]
    map_frame.map = aprx_map
    map_frame.camera.setExtent(extent)
    aprx_map.defaultCamera = map_frame.camera

    escala_ajustada = ((((map_frame.camera.scale * 1.2) // 50) + 1) * 50)
    map_frame.camera.scale = escala_ajustada
    map_frame.camera.setExtent(map_frame.camera.getExtent())


def _ajustar_textos_layout(layout, textos):
    """Substitui o texto de cada TEXT_ELEMENT `{chave}` pelo valor correspondente em `textos`."""
    for chave, valor in textos.items():
        wildcard = f'{{{chave}}}'
        encontrados = layout.listElements(element_type='TEXT_ELEMENT', wildcard=wildcard)
        if not encontrados:
            arcpy.AddWarning(f'Elemento {wildcard} não encontrado no layout.')
            continue
        encontrados[0].text = '' if valor is None else str(valor)


def _formatar_numero_br(valor, casas=2):
    """Formata medidas do carimbo conforme a convenção brasileira."""
    if valor is None or valor == '':
        return ''
    return (
        f'{float(valor):,.{casas}f}'
        .replace(',', 'X')
        .replace('.', ',')
        .replace('X', '.')
    )


def gerar_planta_perimetro(
    bairro_selecionado,
    confrontantes_bairro,
    vertices_bairro,
    bairro,
    municipio,
    area,
    processo,
    perimetro,
    data,
    fusoutm,
    responsavel_tecnico,
    funcao,
    n_crea_cau,
    total_segmentos=None,
    protocolo=None,
):
    """
    Monta a folha 1 (A3) da planta de perímetro: adiciona confrontantes/
    segmentos e vértices ao map frame principal, o bairro/perímetro ao
    overview (com basemap World Imagery), ajusta a escala dos dois map
    frames e preenche o carimbo/cabeçalho. SEM lotes, quadras ou tabela
    de quadras — fora do escopo desta ferramenta.

    Args:
        bairro_selecionado: caminho do polígono do bairro/perímetro.
        confrontantes_bairro: caminho da feição de segmentos/confrontantes
            (linhas) — saída de
            `pipeline_perimetro.montar_tabela_segmentos_de_vertices`.
        vertices_bairro: caminho da feição de pontos dos vértices.
        bairro, municipio, area, processo, perimetro, data, fusoutm,
            responsavel_tecnico, funcao, n_crea_cau: textos do carimbo/
            cabeçalho (mesmo padrão do Núcleo — ver `{chave}` nos
            TEXT_ELEMENTs do layout).
        total_segmentos: quantidade de segmentos do perímetro, usada para
            decidir se o Quadro vai em folha adicional (ver
            `exportar_pdf_unificado.planejar_folhas`). Omitido, é contado
            da própria feição de confrontantes.
        protocolo: número de protocolo do selo de autenticação, estampado
            no carimbo (ver `autenticacao_documentos.montar_selo`).

    Returns:
        tuple[arcpy._mp.Layout, arcpy.mp.ArcGISProject]: layout já
        pronto (PDF ainda não exportado — usar
        `exportar_planta_perimetro_para_pdf` / `exportar_pdf_unificado.exportar_pdf_layout`)
        e o projeto ArcGIS aberto.

    Raises:
        RuntimeError: ArcPy indisponível, ou `project_layout.aprx` /
            layout / map frames ausentes ou incompletos (ver
            `layout/LEIA-ME_LAYOUTS.txt`).
    """
    aprx = _obter_projeto()
    if total_segmentos is None:
        total_segmentos = _contar_segmentos(confrontantes_bairro)
    plano_folhas = planejar_folhas(total_segmentos)
    layout_planta = _obter_layout(aprx, NOME_LAYOUT_PLANTA)
    validar_elementos_layout(layout_planta)
    map_frame_planta = _obter_mapa(aprx, NOME_MAPA_PRINCIPAL)
    map_overview_planta = _obter_mapa(aprx, NOME_MAPA_OVERVIEW)

    camadas_map_frame = (
        (confrontantes_bairro, simbologia_confrontantes),
        (vertices_bairro, simbologia_vertices),
    )
    layer_confrontantes = None
    for camada, simbologia in camadas_map_frame:
        layer = _adicionar_camada(map_frame_planta, camada, simbologia)
        if camada == confrontantes_bairro and layer is not None:
            _ocultar_campos_internos(layer)
            layer.showLabels = False
            layer_confrontantes = layer
        if camada == vertices_bairro and layer is not None:
            _configurar_rotulos_vertices(layer)
    if layer_confrontantes is not None:
        _configurar_tabela_planta(
            layout_planta,
            map_frame_planta,
            confrontantes_bairro,
            layer_confrontantes,
            plano_folhas['tem_anexo'],
        )
        (
            feature_rotulos,
            pontos_rotulos_curtos,
            lado_externo,
        ) = _criar_camadas_rotulos_confrontantes(
            confrontantes_bairro, bairro_selecionado
        )
        layer_rotulos = _adicionar_camada(
            map_frame_planta, feature_rotulos, simbologia_confrontantes
        )
        if layer_rotulos is not None:
            layer_rotulos.definitionQuery = (
                f'comprimento >= {COMPRIMENTO_MINIMO_ROTULO_LINHA_M}'
            )
            _configurar_camada_rotulos(
                layer_rotulos, lado_externo=lado_externo
            )
        layer_rotulos_curtos = _adicionar_camada(
            map_frame_planta, pontos_rotulos_curtos, None
        )
        if layer_rotulos_curtos is not None:
            _configurar_camada_rotulos(
                layer_rotulos_curtos, rotulos_pontuais=True
            )

    _adicionar_camada(map_overview_planta, bairro_selecionado, simbologia_perimetro_overview)
    _adicionar_basemap_imagery(map_overview_planta)

    _ajustar_escala_visualizacao(
        map_frame_planta, layout_planta, bairro_selecionado, NOME_MAPA_PRINCIPAL
    )
    _ajustar_escala_visualizacao(
        map_overview_planta, layout_planta, bairro_selecionado, NOME_MAPA_OVERVIEW
    )

    _ajustar_textos_layout(
        layout_planta,
        {
            'bairro': bairro,
            'municipio': municipio,
            'area': _formatar_numero_br(area),
            'perimetro': _formatar_numero_br(perimetro),
            'data': data,
            'fusoutm': fusoutm,
            'responsavel_tecnico': responsavel_tecnico,
            'funcao': funcao,
            'n_crea_cau': n_crea_cau,
            'processo': processo,
            'matricula': TEXTO_MATRICULA_VAZIA,
            'folha': plano_folhas['folha_planta'],
            'municipio_overview': municipio,
            'protocolo': protocolo or '',
        },
    )
    _preencher_aviso_tabela(layout_planta, plano_folhas)

    return layout_planta, aprx


def exportar_planta_perimetro_para_pdf(layout_planta, out_pdf):
    """Helper fino: exporta a folha 1 já pronta para PDF.

    Ver `exportar_pdf_unificado.exportar_pdf_layout` (mesma implementação,
    reexportada aqui para uso direto de quem já importou este módulo).
    """
    return exportar_pdf_layout(layout_planta, out_pdf)
