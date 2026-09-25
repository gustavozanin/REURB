# -*- coding: utf-8 -*-
"""Orquestra o pipeline geométrico do perímetro (vértices -> tabela final).

Módulo fino que só encadeia, na ordem correta, os módulos ArcPy já
existentes desta ferramenta. Não reimplementa nenhuma lógica geométrica
— cada etapa fica no seu próprio módulo (ver docstring de cada um).

Ordem do pipeline (ver também o cabeçalho de `fluxo_geracao.py`):

    1. `transforma_feicao.transforma_feicao`        -> vértices (pontos, anel fechado)
    2. `fluxo_geracao.aplicar_densidade_vertices`    -> integral ou simplificado
    3. `azimute_utm.calcular_atributos_vertices`     -> E, N, azimute por vértice
    4. `transforma_vertices_em_linhas`               -> segmentos (linhas) + distância
    5. `confrontantes.confrontantes`                 -> preenche campo `confrontantes`
    6. `formatar_tabela_atributos.formatar_tabela_atributos` -> tabela final De/Para/...

Requer ArcPy (roda apenas dentro do ArcGIS Pro). Em ambiente sem ArcPy,
`montar_tabela_segmentos_de_vertices` levanta `RuntimeError` imediatamente,
mas a função já está pronta para ser chamada assim que houver uma sessão
Pro disponível (Fase 3 fará essa ligação a partir da toolbox).
"""

try:
    import arcpy
except ImportError:
    arcpy = None

import confrontantes as confrontantes_mod
import formatar_tabela_atributos
import motor_perimetro


def montar_tabela_segmentos_de_vertices(
    feicao_perimetro,
    n_coletivo,
    bairro_feicoes,
    confrontante_feicoes,
    eixo_viario,
    densidade='integral',
    tolerancia_m=0.5,
    messages=None,
):
    """
    Executa o pipeline geométrico completo do perímetro: extrai vértices,
    aplica densidade, calcula azimute/E/N em UTM, gera segmentos, resolve
    confrontantes e monta a tabela final de atributos (De/Para/Azimute/
    Distância/E/N/Confrontantes).

    Args:
        feicao_perimetro: caminho do polígono do perímetro (já no SR UTM
            do fuso do processo).
        n_coletivo: número do REURB coletivo (usado para excluir o
            próprio bairro da busca de confrontantes vizinhos).
        bairro_feicoes: camada/feição de bairros (FeatureServer layer 8).
        confrontante_feicoes: camada "Confrontante Externo" (FeatureServer layer 1).
        eixo_viario: camada de eixo viário (FeatureServer layer 0).
        densidade: 'integral' ou 'simplificado'.
        tolerancia_m: tolerância (m) da simplificação colinear (só usada
            quando densidade='simplificado').
        messages: objeto de mensagens da toolbox (opcional).

    Returns:
        tuple[os.PathLike, os.PathLike]: `(tabela_final, vertices)` — a
        feição final de segmentos (campos de, para, azimute, distancia,
        E, N e confrontantes) e a feição de pontos dos vértices (já com
        densidade aplicada e atributos E/N/azimute calculados), usada
        pelo map frame da planta (`gerar_planta_perimetro.py`).

    Raises:
        RuntimeError: se ArcPy não estiver disponível neste ambiente.
    """
    if arcpy is None:
        raise RuntimeError('arcpy necessário para montar_tabela_segmentos_de_vertices.')

    if densidade != 'integral':
        arcpy.AddWarning(
            'A simplificação foi desabilitada para o memorial: a geometria '
            'integral é obrigatória para preservar o perímetro jurídico.'
        )
    segmentos, vertices, auditoria = motor_perimetro.gerar_vertices_segmentos(
        feicao_perimetro
    )

    confrontantes_mod.confrontantes(
        feicao_entrada=segmentos,
        n_coletivo=n_coletivo,
        bairro_feicoes=bairro_feicoes,
        confrontante_feicoes=confrontante_feicoes,
        eixo_viario=eixo_viario,
    )

    tabela_final = formatar_tabela_atributos.formatar_tabela_atributos(segmentos)

    return tabela_final, vertices, auditoria
