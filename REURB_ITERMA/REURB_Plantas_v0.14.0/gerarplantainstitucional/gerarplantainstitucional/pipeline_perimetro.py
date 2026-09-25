# -*- coding: utf-8 -*-
"""Orquestra o pipeline geométrico do perímetro (vértices -> tabela final).

Módulo fino que só encadeia, na ordem correta, os módulos ArcPy já
existentes desta ferramenta. Não reimplementa nenhuma lógica geométrica
— cada etapa fica no seu próprio módulo (ver docstring de cada um).

Ordem do pipeline (ver também o cabeçalho de `fluxo_geracao.py`):

    1. `motor_perimetro.gerar_vertices_segmentos` -> vértices + segmentos
       (anel integral; azimute/E/N/distância no plano UTM)
    2. `confrontantes` (bairro) ou `confrontantes_lote` (lote institucional)
    3. `formatar_tabela_atributos.formatar_tabela_atributos` -> tabela final

Requer ArcPy (roda apenas dentro do ArcGIS Pro). Em ambiente sem ArcPy,
`montar_tabela_segmentos_de_vertices` levanta `RuntimeError` imediatamente.
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
    lote_feicoes=None,
    quadra=None,
    lote=None,
):
    """
    Executa o pipeline geométrico completo: vértices, segmentos e
    confrontantes.

    Com ``lote_feicoes`` + ``lote`` usa a ordem de lote (vizinhos → FS1
    → eixo). Sem isso, mantém a ordem de perímetro de bairro.
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

    if lote_feicoes is not None:
        if lote is None:
            raise RuntimeError(
                'lote_feicoes exige o parâmetro lote (exclusão do próprio lote).'
            )
        confrontantes_mod.confrontantes_lote(
            feicao_entrada=segmentos,
            n_coletivo=n_coletivo,
            quadra=quadra,
            lote=lote,
            lote_feicoes=lote_feicoes,
            confrontante_feicoes=confrontante_feicoes,
            eixo_viario=eixo_viario,
            poligono_lote=feicao_perimetro,
        )
    else:
        confrontantes_mod.confrontantes(
            feicao_entrada=segmentos,
            n_coletivo=n_coletivo,
            bairro_feicoes=bairro_feicoes,
            confrontante_feicoes=confrontante_feicoes,
            eixo_viario=eixo_viario,
        )

    tabela_final = formatar_tabela_atributos.formatar_tabela_atributos(segmentos)

    return tabela_final, vertices, auditoria
